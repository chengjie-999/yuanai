"""P1 终端对话 CLI（产品愿景：终端对话 → 宠物对话）

v2 企业级重构（2026-10-25）：
- **rich** 渲染：REPL 里回答以 Markdown 流式渲染（标题/粗体/表格/代码块
  pygments 着色），回答块带边框面板；管道模式保持纯文本输出
- **prompt_toolkit** 交互：多行输入（粘贴代码不碎行，Enter 提交 /
  Esc+Enter 换行）、跨会话命令历史（data/terminal_history.txt）、
  ↑↓ 历史 / 光标编辑；Ctrl+C 第一下停止本轮生成回到提示符，空闲时再按退出
- /chat 与 /claude 统一流式输出（llm.astream / SDK loop），不再全文突现

`python -m agent.terminal` 在 Windows 终端里直接对话本机 Claude Code / 本地 LLM。
零配置纯本地：默认 /claude 复用 agent/claude_loop.py 的 anthropic SDK loop
（凭证 env > ~/.claude/.credentials.json，与桥接一致），审批流在终端内 Y/N
裁决；/chat 切本地 LLM 直连（deepseek-flash，yuanai_core.core.lc.get_llm）。

用法:
    python -m agent.terminal                     # REPL 交互（自动续接上次会话）
    python -m agent.terminal --new               # 强制开新会话
    python -m agent.terminal --session <id>      # 续接指定会话
    echo "看看项目结构" | python -m agent.terminal   # 管道单轮（不落盘会话）

命令:
    /claude   切本机 Claude Code（默认；SDK loop + 工具 + 审批 Y/N）
    /chat     切本地 LLM 直连（deepseek-flash）
    /history  列出历史会话
    /clear    清空当前会话消息
    /quit     退出

设计要点：
- 会话续接独立文件 data/terminal_sessions.json（不与云端桥接 claude_sessions.json 互串）
- 安全沿用桥接口径：cwd 锁仓库根（CC_PROJECT_DIR 可指真实仓库）、工具执行
  经 claude_loop.execute_tool 的安全分类（deny 拒绝 / review 审批）
- 桌宠联动：思考→thinking、工具→working+工具名、审批→attention、完成→idle、报错→error
- 模型可配 env TERMINAL_CHAT_MODEL（默认 deepseek-flash）；CLAUDE_BRIDGE_MODEL /
  CLAUDE_BRIDGE_THINKING 对 /claude 生效（复用 claude_loop 读取）
"""

from __future__ import annotations  # 惰性注解：Python 3.8 下 `dict | None` 不再在定义时求值

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_path import root_path  # noqa: E402

# 冻结版仓库目录解析（同 claude_bridge）：exe 内 root_path() 指向数据目录
# 而非真实仓库——发布版可设 CC_PROJECT_DIR 指向真实仓库；未设置保持 fail-closed。
_CC_DIR = os.getenv("CC_PROJECT_DIR", "")
if _CC_DIR and os.path.isdir(_CC_DIR):
    PROJECT_ROOT = os.path.abspath(_CC_DIR)
else:
    PROJECT_ROOT = root_path()

SESSIONS_FILE = os.path.join(PROJECT_ROOT, "data", "terminal_sessions.json")
HISTORY_FILE = os.path.join(PROJECT_ROOT, "data", "terminal_history.txt")
DEFAULT_CHAT_MODEL = os.getenv("TERMINAL_CHAT_MODEL", "deepseek-flash")
MAX_TOOL_OUTPUT = 2000   # 终端回显工具输出截断（对齐 claude_bridge）
MAX_SESSIONS = 50        # 会话文件保留上限
MAX_STORED_MSGS = 200    # 每会话落盘消息上限（防文件无限增长）
MAX_SENT_MSGS = 100      # 每轮发送模型的历史上限（SDK 全量重发，必须封顶）

try:
    # errors="replace"：第三方网关流可能含孤立 surrogate（解码脏字节）——
    # utf-8 严格编码会 UnicodeEncodeError 打断整轮对话，替换为 '?' 兜底
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ———————— ANSI 颜色（PlainRenderer 用；仅 tty 输出，管道模式纯文本） ————————
_TTY = sys.stdout.isatty()
GRAY = "\x1b[90m" if _TTY else ""
CYAN = "\x1b[96m" if _TTY else ""
YELLOW = "\x1b[93m" if _TTY else ""
RED = "\x1b[91m" if _TTY else ""
RESET = "\x1b[0m" if _TTY else ""

_CHAT_SYSTEM_PROMPT = (
    "你是小元AI 本机终端助手（本地 LLM 直连模式），用户在本机 Windows 终端与你对话。"
    "用简洁中文回答，涉及代码时给可复制的命令。"
)


# ==================== 会话存储 ====================

class TerminalSessionStore:
    """终端会话持久化：data/terminal_sessions.json（独立于云端桥接映射）。

    结构: {"last": <id>, "sessions": [{id, mode, messages, created, updated}]}
    消息统一 {"role": "user"|"assistant", "content": str}——SDK loop 与 /chat
    两种模式共用同一形状，模式切换不清空历史。
    """

    def __init__(self, path: str = SESSIONS_FILE):
        self._path = path
        self._data = {"last": None, "sessions": []}
        self._sessions: dict = {}

    def load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("sessions"), list):
                self._data = data
                self._sessions = {s.get("id"): s for s in data["sessions"]
                                  if isinstance(s, dict) and s.get("id")}
        except (OSError, ValueError):
            self._data = {"last": None, "sessions": []}
            self._sessions = {}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except OSError as e:
            print(f"{RED}会话保存失败: {e}{RESET}", file=sys.stderr)

    def new_session(self, mode: str) -> dict:
        sid = uuid.uuid4().hex[:12]
        s = {"id": sid, "mode": mode, "messages": [],
             "created": time.time(), "updated": time.time()}
        self._sessions[sid] = s
        self._data["sessions"].append(s)
        if len(self._data["sessions"]) > MAX_SESSIONS:
            for old in self._data["sessions"][:-MAX_SESSIONS]:
                self._sessions.pop(old.get("id"), None)
            self._data["sessions"] = self._data["sessions"][-MAX_SESSIONS:]
        self._data["last"] = sid
        self._save()
        return s

    def get(self, sid: str) -> dict | None:
        return self._sessions.get(sid)

    def latest(self) -> dict | None:
        last = self._data.get("last")
        if last and last in self._sessions:
            return self._sessions[last]
        sessions = sorted(self._sessions.values(), key=lambda s: s.get("updated", 0))
        return sessions[-1] if sessions else None

    def append(self, sid: str, role: str, content: str, mode: str) -> None:
        s = self._sessions.get(sid)
        if not s:
            return
        # 孤立 surrogate 清洗（网关流脏字节解码产物）——否则 json 落盘 utf-8 编码失败
        content = _clean_text(content)
        s["messages"].append({"role": role, "content": content})
        if len(s["messages"]) > MAX_STORED_MSGS:
            s["messages"] = s["messages"][-MAX_STORED_MSGS:]
        s["mode"] = mode
        s["updated"] = time.time()
        self._data["last"] = sid
        self._save()

    def clear(self, sid: str) -> None:
        s = self._sessions.get(sid)
        if not s:
            return
        s["messages"] = []
        s["updated"] = time.time()
        self._save()


# ==================== 编码防护 ====================

def _clean_text(text: str) -> str:
    """清洗孤立 surrogate（Windows 管道 GBK/UTF-8 解码错位、网关流脏字节的产物）。

    anthropic SDK 请求序列化是严格 utf-8 编码——带 surrogate 的字符串会让
    openapi_dumps 抛 UnicodeEncodeError 打断整轮对话；清洗后落盘/回传均安全。
    """
    return text.encode("utf-8", errors="replace").decode("utf-8")


def read_stdin_query() -> str:
    """按字节读 stdin 并容错解码：utf-8 优先、GBK 兜底（中文 Windows 终端/管道
    双形态）。绕过 sys.stdin 默认 surrogateescape（脏字节会变成 surrogate 混入请求）。"""
    raw = sys.stdin.buffer.read()
    for enc in ("utf-8", "gbk"):
        try:
            return _clean_text(raw.decode(enc).strip())
        except UnicodeDecodeError:
            continue
    return _clean_text(raw.decode("utf-8", errors="replace").strip())


def find_terminal_launcher():
    """探测可启动终端的 (python_exe, project_root)；不可用返回 None。

    托盘「终端对话」入口用（三本地合一：Agent 常驻 + 桌宠 + 终端统一托盘托管）：
    - 源码树运行（托盘由项目 venv python 跑）：复用当前解释器 + 仓库根
    - 冻结 exe：向上探测仓库布局（venv\\Scripts\\python.exe + agent\\terminal.py）
      ——开发机 dist\\ 下的 exe 能探到项目 venv；发布版无源码环境返回 None
    """
    if not getattr(sys, "frozen", False):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return (sys.executable, root) if os.path.isfile(os.path.join(root, "agent", "terminal.py")) else None
    exe_dir = Path(sys.executable).resolve().parent
    for base in (exe_dir, exe_dir.parent, exe_dir.parent.parent, exe_dir.parent.parent.parent):
        venv_py = base / "venv" / "Scripts" / "python.exe"
        if venv_py.is_file() and (base / "agent" / "terminal.py").is_file():
            return (str(venv_py), str(base))
    return None


# ==================== 渲染层（v2 抽象：管道纯文本 / tty rich 流式） ====================

class PlainRenderer:
    """管道/测试渲染：纯文本直接打 stdout（capsys 可断言）"""

    def token(self, text: str) -> None:
        print(text, end="", flush=True)

    def reasoning(self, text: str) -> None:
        print(f"{GRAY}{text}{RESET}", end="", flush=True)

    def tool_start(self, name: str) -> None:
        print(f"\n{CYAN}⚙ {name}{RESET}", flush=True)

    def tool_end(self, name: str, output: str) -> None:
        out = output if len(output) <= MAX_TOOL_OUTPUT else output[:MAX_TOOL_OUTPUT] + "\n...(输出过长已截断)"
        print(f"{GRAY}{out}{RESET}", flush=True)

    def done(self) -> None:
        print(flush=True)

    def error(self, text: str) -> None:
        print(f"\n{RED}✗ {text}{RESET}", flush=True)

    def info(self, text: str) -> None:
        print(f"{GRAY}{text}{RESET}", flush=True)

    def interrupted(self) -> None:
        print(f"\n{YELLOW}（已停止生成）{RESET}", flush=True)


class RichRenderer:
    """tty REPL 渲染：rich Live 流式 Markdown（代码块 pygments 着色）+ 面板回答块"""

    def __init__(self, console=None):
        from rich.console import Console
        self._console = console or Console()
        self._answer = ""      # 回答 markdown 累积
        self._reasoning = ""   # 思考累积
        self._live = None
        try:
            dark = os.getenv("TERMINAL_DARK", "1") == "1"
        except Exception:
            dark = True
        self._code_theme = "github-dark" if dark else "github-light"

    def _refresh(self) -> None:
        from rich.live import Live
        from rich.markdown import Markdown
        from rich.text import Text
        from rich.console import Group
        if self._live is None:
            self._live = Live(Group(), console=self._console, refresh_per_second=12)
            self._live.start()
        parts = []
        if self._reasoning:
            parts.append(Text("思考中…\n" + self._reasoning, style="dim italic"))
        parts.append(Markdown(self._answer or "…", code_theme=self._code_theme))
        self._live.update(Group(*parts))

    def _stop_live(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None

    def token(self, text: str) -> None:
        self._answer += text
        self._refresh()

    def reasoning(self, text: str) -> None:
        self._reasoning += text
        self._refresh()

    def tool_start(self, name: str) -> None:
        self._stop_live()
        self._console.print(f"[yellow]⚙[/yellow] [bold]{name}[/bold]")

    def tool_end(self, name: str, output: str) -> None:
        from rich.text import Text
        out = output if len(output) <= MAX_TOOL_OUTPUT else output[:MAX_TOOL_OUTPUT] + "\n...(输出过长已截断)"
        self._console.print(Text(out, style="dim"))

    def done(self) -> None:
        self._stop_live()
        if self._answer:
            from rich.markdown import Markdown
            from rich.panel import Panel
            self._console.print(Panel(
                Markdown(self._answer, code_theme=self._code_theme),
                border_style="bright_black", padding=(0, 1),
            ))

    def error(self, text: str) -> None:
        self._stop_live()
        self._console.print(f"[red]✗ {text}[/red]")

    def info(self, text: str) -> None:
        self._stop_live()
        self._console.print(f"[dim]{text}[/dim]")

    def interrupted(self) -> None:
        self._stop_live()
        self._console.print("[yellow]（已停止生成）[/yellow]")


# ==================== 查询执行（render 注入，v2 统一流式） ====================

def _emit_pet(state: str, tool: str = None) -> None:
    """桌宠事件（失败静默，不阻塞终端）"""
    try:
        from agent.pet_events import emit
        emit(state=state, tool=tool)
    except Exception:
        pass


def _approve_yn(decision_id: str, tool_name: str, command: str) -> str:
    """管道/纯文本模式审批：Y/N 交互；空输入/非法输入 = deny（fail-closed）"""
    _emit_pet("attention")
    ans = input(f"{YELLOW}  ⚠ 审批 [{tool_name}] `{str(command)[:120]}` 执行? [y/N] {RESET}")
    return "approve" if ans.strip().lower() in ("y", "yes") else "deny"


async def run_claude_query(messages: list, on_approval=None, render=None) -> str:
    """/claude 模式：复用 claude_loop SDK loop（与云端桥接同一条代码路径）"""
    from agent.claude_loop import run_sdk_loop, load_credentials, BRIDGE_SYSTEM_PROMPT

    render = render or PlainRenderer()
    api_key = load_credentials()
    if not api_key:
        render.error("未找到 Anthropic 凭证（ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / "
                     "~/.claude/.credentials.json）——请配置后重试，或 /chat 切本地 LLM")
        return ""

    _emit_pet("thinking")
    final = ""
    async for ev in run_sdk_loop(messages, api_key=api_key,
                                 system=BRIDGE_SYSTEM_PROMPT,
                                 on_approval=on_approval):
        kind = ev.get("type", "")
        if kind == "token":
            render.token(_clean_text(ev["data"]))
        elif kind == "reasoning":
            render.reasoning(_clean_text(ev["data"]))
        elif kind == "tool_start":
            _emit_pet("working", tool=ev["data"]["name"])
            render.tool_start(ev["data"]["name"])
        elif kind == "tool_end":
            render.tool_end(ev["data"]["name"], _clean_text(ev["data"]["output"]))
            _emit_pet("thinking")
        elif kind == "approval":
            pass  # 审批提示由 on_approval 直接打印
        elif kind == "done":
            final = _clean_text(ev["data"].get("display_content", ""))
            render.done()
            _emit_pet("idle")
        elif kind == "error":
            render.error(_clean_text(ev["data"]))
            if "SDK 未安装" in str(ev["data"]):
                render.info("请用项目 venv 运行：venv\\Scripts\\python.exe -m agent.terminal")
            _emit_pet("error")
    return final


async def run_chat_query(messages: list, render=None) -> str:
    """本地 LLM 直连（/chat 模式，v2 流式：llm.astream 逐块输出）"""
    from yuanai_core.core.lc import get_llm
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    render = render or PlainRenderer()
    try:
        from yuanai_core.core.lc import get_llm as _get
        from langchain_core.messages import SystemMessage as _S, HumanMessage as _H, AIMessage as _A
        llm_messages = [_S(content=_CHAT_SYSTEM_PROMPT)]
        for m in messages[-MAX_SENT_MSGS:]:
            content = m.get("content", "")
            if not content.strip():
                continue
            llm_messages.append(_H(content=content) if m["role"] == "user" else _A(content=content))
        llm = get_llm(DEFAULT_CHAT_MODEL, temperature=0.1)
    except Exception as e:
        render.error(f"本地 LLM 依赖不可用: {str(e)[:160]}——请用项目 venv 运行："
                     "venv\\Scripts\\python.exe -m agent.terminal")
        _emit_pet("error")
        return ""

    _emit_pet("thinking")
    final = ""
    try:
        async for chunk in llm.astream(llm_messages):
            text = chunk.content if hasattr(chunk, "content") else str(chunk)
            if not text:
                continue
            clean = _clean_text(text)
            final += clean
            render.token(clean)
    except Exception as e:
        render.error(f"本地 LLM 调用失败: {str(e)[:200]}")
        _emit_pet("error")
        return "" if not final else final
    if not final:
        render.error("本地 LLM 返回空（检查模型配置/API Key）")
        _emit_pet("error")
        return ""
    render.done()
    _emit_pet("idle")
    return final


async def run_query(mode: str, messages: list, on_approval=None, render=None) -> str:
    """按模式执行一轮；返回助手最终文本（空串 = 无产出/失败）"""
    history = messages[-MAX_SENT_MSGS:]
    if mode == "chat":
        return await run_chat_query(history, render=render)
    return await run_claude_query(history, on_approval=on_approval, render=render)


# ==================== REPL（prompt_toolkit 企业级交互） ====================

async def _ainput(prompt: str = "") -> str:
    """纯文本模式输入（测试可 mock 的默认实现）"""
    line = await asyncio.get_running_loop().run_in_executor(None, input, prompt)
    return _clean_text(line).strip()


def _make_ptk_prompt(mode_ref) -> object:
    """prompt_toolkit PromptSession（惰性构造一次复用）：
    - 多行输入：Enter 提交 / Esc+Enter 换行——粘贴多行代码不碎行
    - FileHistory 跨会话历史（↑↓ 找回、左右编辑）
    - Ctrl+C → KeyboardInterrupt 冒泡（空闲退出/生成中停止）
    返回 prompt_fn = async () -> str | None（None = EOF 退出）"""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.formatted_text import ANSI

    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    @kb.add("escape", "enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    session = PromptSession(
        multiline=True, key_bindings=kb,
        history=FileHistory(HISTORY_FILE),
    )

    async def prompt_fn() -> str | None:
        try:
            mode = mode_ref[0]
            p = f"小元[{mode}]> " if mode != "claude" else "小元> "
            text = await session.prompt_async(ANSI(p))
            return text.strip()
        except EOFError:
            return None

    return prompt_fn


async def _ptk_approve(tool_name: str, command: str) -> str:
    """rich REPL 的审批：prompt_toolkit 单行确认（与主输入会话分离）"""
    from prompt_toolkit.shortcuts import prompt_async
    from prompt_toolkit.formatted_text import ANSI

    _emit_pet("attention")
    try:
        ans = await prompt_async(
            ANSI(f"[yellow]  ⚠ 审批 [{tool_name}] `{str(command)[:120]}` 执行? [y/N] [/yellow]"),
            default="N")
    except (EOFError, KeyboardInterrupt):
        return "deny"
    return "approve" if ans.strip().lower() in ("y", "yes") else "deny"


def _print_help(render) -> None:
    render.info("命令: /claude 本机Claude(默认)  /chat 本地LLM  /history 历史会话  "
                "/clear 清空当前会话  /quit 退出")


async def _list_history(store: TerminalSessionStore, render) -> None:
    sessions = sorted(store._sessions.values(), key=lambda s: s.get("updated", 0), reverse=True)
    if not sessions:
        render.info("(暂无历史会话)")
        return
    for s in sessions:
        first = next((m["content"][:30] for m in s.get("messages", []) if m["role"] == "user"), "(空会话)")
        render.info(f"[{s['id']}] {s.get('mode', 'claude')}  {len(s.get('messages', []))} 条  "
                    f"{time.strftime('%m-%d %H:%M', time.localtime(s.get('updated', 0)))}  {first}")


async def run_repl(session: dict, store: TerminalSessionStore,
                   prompt_fn=None, render=None) -> None:
    """REPL 主循环。prompt_fn: async () -> str|None（None=退出）——默认
    rich 模式用 prompt_toolkit，纯文本模式用 _ainput（测试可注入 mock）。"""
    mode = session.get("mode", "claude")
    mode_ref = [mode]
    rich_mode = render is not None and isinstance(render, RichRenderer)
    render = render or PlainRenderer()
    if prompt_fn is None:
        if rich_mode:
            try:
                prompt_fn = _make_ptk_prompt(mode_ref)
            except Exception:
                # 非 Windows 控制台（Git Bash mintty 未加 winpty 等）：交互层回退
                # 基础 input()，rich 渲染保留
                render.info("当前终端不支持交互增强（需 cmd/PowerShell/Windows Terminal），"
                            "已回退基础输入模式")
                rich_mode = False
        if prompt_fn is None:
            async def _plain_prompt():
                try:
                    return await _ainput(f"小元[{mode_ref[0]}]> ")
                except (EOFError, KeyboardInterrupt):
                    return None
            prompt_fn = _plain_prompt

    render.info(f"小元AI 终端对话 — 模式: {mode} | 会话: {session.get('id', '')} | /help 查看命令")

    while True:
        try:
            line = await prompt_fn()
        except KeyboardInterrupt:
            # 空闲时 Ctrl+C = 退出
            print()
            break
        if line is None:
            break
        line = line.strip()
        if not line:
            continue
        if line.startswith("/"):
            cmd = line.split(maxsplit=1)[0].lower()
            if cmd == "/quit":
                break
            elif cmd == "/clear":
                store.clear(session["id"])
                render.info(f"当前会话已清空（{session['id']}）")
            elif cmd == "/history":
                await _list_history(store, render)
            elif cmd == "/help":
                _print_help(render)
            elif cmd == "/claude":
                mode = "claude"; mode_ref[0] = mode
                render.info("已切换本机 Claude Code 模式")
            elif cmd == "/chat":
                mode = "chat"; mode_ref[0] = mode
                render.info(f"已切换本地 LLM 直连模式（{DEFAULT_CHAT_MODEL}）")
            else:
                render.info(f"未知命令: {cmd}（/help 查看）")
            continue
        store.append(session["id"], "user", line, mode)

        # 审批回调：rich 模式走 ptk prompt_async（主循环线程）；纯文本走 input()
        if rich_mode:
            main_loop = asyncio.get_running_loop()

            def on_approval(decision_id, tool_name, command):
                fut = asyncio.run_coroutine_threadsafe(
                    _ptk_approve(tool_name, command), main_loop)
                try:
                    return fut.result(timeout=120)
                except Exception:
                    return "deny"
        else:
            on_approval = _approve_yn

        task = asyncio.create_task(
            run_query(mode, session["messages"], on_approval=on_approval, render=render))
        try:
            result = await task
        except KeyboardInterrupt:
            # Ctrl+C 第一下：停止本轮生成，回到提示符（v2 语义）
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            render.interrupted()
            _emit_pet("idle")
            continue
        if result.strip():
            store.append(session["id"], "assistant", result, mode)


async def run_pipe(query: str, mode: str, render=None) -> None:
    """管道模式：单轮输出、不落盘会话（脚本化场景，纯文本）"""
    messages = [{"role": "user", "content": query}]
    await run_query(mode, messages, on_approval=_approve_yn, render=render)


def parse_args():
    p = argparse.ArgumentParser(description="小元AI 终端对话 CLI（默认 /claude 本机 Claude Code）")
    p.add_argument("--new", action="store_true", help="强制开新会话（默认自动续接上次会话）")
    p.add_argument("--session", default=None, help="续接指定会话 ID（/history 查看）")
    p.add_argument("--mode", default="claude", choices=["claude", "chat"],
                   help="启动模式：claude=本机 Claude Code（默认）/ chat=本地 LLM")
    p.add_argument("--install-yuan", action="store_true",
                   help="把 yuan 命令装进用户 PATH（仿 claude：任何目录直接 yuan 启动）")
    return p.parse_args()


def install_yuan_command() -> int:
    """把 `yuan` / `yuancc` / `yuanagent` 装进用户 PATH（仿 claude 命令，2026-10-25 用户拍板）：
    - yuan      = 小元自建 v2 终端（/claude SDK loop + /chat 本地 LLM + 桌宠 + 自有会话）
    - yuancc    = Claude Code 原生终端（参数透传：yuancc -p "问题" = claude -p）
    - yuanagent = 本地 Agent 命令行形态（终端命令安装/启动：yuanagent --install <安装码>
                  注册 / --tray 托盘 / 默认后台运行——源码环境免 exe 下载）
    ① 生成三个 .bat（内嵌仓库路径 + venv python，ASCII 内容防 cmd GBK 误读）
       到 %LOCALAPPDATA%\\yuan\\
    ② 该目录追加进用户 PATH（PowerShell 用户级写回，防 setx 1024 截断；幂等）"""
    import subprocess
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    inst_dir = os.path.join(local, "yuan")
    os.makedirs(inst_dir, exist_ok=True)

    yuan_bat = os.path.join(inst_dir, "yuan.bat")
    with open(yuan_bat, "w", encoding="ascii") as f:
        f.write('@echo off\n')
        f.write('rem XiaoYuanAI built-in terminal (installed by --install-yuan)\n')
        f.write(f'cd /d "{repo}"\n')
        f.write('venv\\Scripts\\python.exe -m agent.terminal %*\n')
        f.write('exit /b %errorlevel%\n')

    yuancc_bat = os.path.join(inst_dir, "yuancc.bat")
    with open(yuancc_bat, "w", encoding="ascii") as f:
        f.write('@echo off\n')
        f.write('rem XiaoYuanAI - yuancc = Claude Code native terminal (thin wrapper)\n')
        f.write('where claude >nul 2>nul\n')
        f.write('if errorlevel 1 goto no_claude\n')
        f.write('claude %*\n')
        f.write('exit /b %errorlevel%\n')
        f.write('\n')
        f.write(':no_claude\n')
        f.write('echo [yuancc] Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code\n')
        f.write('exit /b 1\n')

    yuanagent_bat = os.path.join(inst_dir, "yuanagent.bat")
    with open(yuanagent_bat, "w", encoding="ascii") as f:
        f.write('@echo off\n')
        f.write('rem XiaoYuanAI local agent - terminal install/launch (no exe download needed)\n')
        f.write(f'cd /d "{repo}"\n')
        f.write('venv\\Scripts\\python.exe -m agent.main %*\n')
        f.write('exit /b %errorlevel%\n')

    ps = (
        "$p=[Environment]::GetEnvironmentVariable('Path','User');"
        f"if(';{inst_dir};' -notlike '*;'+$p+';*'){{"
        f"[Environment]::SetEnvironmentVariable('Path',$p.TrimEnd(';')+';{inst_dir}','User')}}"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"PATH 注册失败: {r.stderr}", file=sys.stderr)
        return 1
    print(f"✅ yuan / yuancc / yuanagent 已安装到: {inst_dir}")
    print("   新开一个终端窗口即可使用：")
    print("   yuan       = 小元自建终端（/claude 默认 + /chat 本地 LLM + 桌宠联动）")
    print('   yuancc     = Claude Code 原生终端（yuancc -p "问题" 管道单轮）')
    print("   yuanagent  = 本地 Agent（--install <安装码> 注册 / --tray 托盘 / 默认后台）")
    return 0


async def main():
    args = parse_args()
    if args.install_yuan:
        sys.exit(install_yuan_command())
    store = TerminalSessionStore()
    store.load()

    if not sys.stdin.isatty():
        # 管道模式：echo "问题" | python -m agent.terminal
        query = read_stdin_query()
        if not query:
            print("用法: echo \"问题\" | python -m agent.terminal", file=sys.stderr)
            return
        await run_pipe(query, args.mode)
        return

    session = None
    if args.session:
        session = store.get(args.session)
        if not session:
            print(f"{RED}会话不存在: {args.session}（/history 查看可用 ID）{RESET}", file=sys.stderr)
            return
    if session is None and not args.new:
        session = store.latest()
        if session and session.get("messages"):
            print(f"{GRAY}已续接上次会话 {session['id']}（{len(session['messages'])} 条历史；"
                  f"--new 开新会话）{RESET}")
    if session is None:
        session = store.new_session(args.mode)
    await run_repl(session, store, render=RichRenderer())


if __name__ == "__main__":
    asyncio.run(main())
