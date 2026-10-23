"""P1 终端对话 CLI（产品愿景：终端对话 → 宠物对话）

`python -m agent.terminal` 在 Windows 终端里直接对话本机 Claude Code / 本地 LLM。
零配置纯本地：默认 /claude 复用 agent/claude_loop.py 的 anthropic SDK loop
（凭证 env > ~/.claude/.credentials.json，与桥接一致），审批流在终端内 Y/N
裁决；/chat 切本地 LLM 直连（deepseek-flash，yuanai_core.core.lc.call_llm）。

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

设计要点（2026-10-23，与用户对齐）:
- 会话续接独立文件 data/terminal_sessions.json（不与云端桥接 claude_sessions.json 互串）
- 安全沿用桥接口径：cwd 锁仓库根（CC_PROJECT_DIR 可指真实仓库）、工具执行
  经 claude_loop.execute_tool 的安全分类（deny 拒绝 / review 审批）
- 桌宠联动：思考→thinking、工具→working+工具名、审批→attention、完成→idle、报错→error
- 模型可配 env TERMINAL_CHAT_MODEL（默认 deepseek-flash）；CLAUDE_BRIDGE_MODEL /
  CLAUDE_BRIDGE_THINKING 对 /claude 生效（复用 claude_loop 读取）
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid

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

# ———————— ANSI 颜色（仅 tty 输出；管道模式纯文本） ————————
_TTY = sys.stdout.isatty()
DIM = "\x1b[90m" if _TTY else ""
GRAY = "\x1b[90m" if _TTY else ""
CYAN = "\x1b[96m" if _TTY else ""
YELLOW = "\x1b[93m" if _TTY else ""
RED = "\x1b[91m" if _TTY else ""
RESET = "\x1b[0m" if _TTY else ""

_CHAT_SYSTEM_PROMPT = (
    "你是小元AI 本机终端助手（本地 LLM 直连模式），用户在本机 Windows 终端与你对话。"
    "用简洁中文回答，涉及代码时给可复制的命令。"
)


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
        # 保留最近 MAX_SESSIONS 个
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


# ==================== 渲染 ====================

def render_token(text: str) -> None:
    print(text, end="", flush=True)


def render_reasoning(text: str) -> None:
    print(f"{GRAY}{text}{RESET}", end="", flush=True)


def render_tool_start(name: str) -> None:
    print(f"\n{CYAN}⚙ {name}{RESET}", flush=True)


def render_tool_end(name: str, output: str) -> None:
    out = output if len(output) <= MAX_TOOL_OUTPUT else output[:MAX_TOOL_OUTPUT] + "\n...(输出过长已截断)"
    print(f"{GRAY}{out}{RESET}", flush=True)


def render_error(text: str) -> None:
    print(f"\n{RED}✗ {text}{RESET}", flush=True)


def render_done() -> None:
    print(flush=True)


# ==================== 查询执行 ====================

def _emit_pet(state: str, tool: str = None) -> None:
    """桌宠事件（失败静默，不阻塞终端）"""
    try:
        from agent.pet_events import emit
        emit(state=state, tool=tool)
    except Exception:
        pass


def _approve_yn(decision_id: str, tool_name: str, command: str) -> str:
    """终端内审批：Y/N 交互；空输入/非法输入 = deny（fail-closed，对齐桥接）"""
    _emit_pet("attention")
    ans = input(f"{YELLOW}  ⚠ 审批 [{tool_name}] `{str(command)[:120]}` 执行? [y/N] {RESET}")
    return "approve" if ans.strip().lower() in ("y", "yes") else "deny"


async def run_claude_query(messages: list, on_approval=None) -> str:
    """/claude 模式：复用 claude_loop SDK loop（与云端桥接同一条代码路径）"""
    from agent.claude_loop import run_sdk_loop, load_credentials, BRIDGE_SYSTEM_PROMPT

    api_key = load_credentials()
    if not api_key:
        render_error("未找到 Anthropic 凭证（ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / "
                     "~/.claude/.credentials.json）——请配置后重试，或 /chat 切本地 LLM")
        return ""

    _emit_pet("thinking")
    final = ""
    async for ev in run_sdk_loop(messages, api_key=api_key,
                                 system=BRIDGE_SYSTEM_PROMPT,
                                 on_approval=on_approval):
        kind = ev.get("type", "")
        if kind == "token":
            render_token(_clean_text(ev["data"]))
        elif kind == "reasoning":
            render_reasoning(_clean_text(ev["data"]))
        elif kind == "tool_start":
            _emit_pet("working", tool=ev["data"]["name"])
            render_tool_start(ev["data"]["name"])
        elif kind == "tool_end":
            render_tool_end(ev["data"]["name"], _clean_text(ev["data"]["output"]))
            _emit_pet("thinking")
        elif kind == "approval":
            pass  # 审批提示由 _approve_yn 直接打印
        elif kind == "done":
            final = _clean_text(ev["data"].get("display_content", ""))
            render_done()
            _emit_pet("idle")
        elif kind == "error":
            render_error(_clean_text(ev["data"]))
            _emit_pet("error")
    return final


async def run_chat_query(messages: list) -> str:
    """本地 LLM 直连（/chat 模式）"""
    from yuanai_core.core.lc import call_llm
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    llm_messages = [SystemMessage(content=_CHAT_SYSTEM_PROMPT)]
    for m in messages[-MAX_SENT_MSGS:]:
        content = m.get("content", "")
        if not content.strip():
            continue
        llm_messages.append(HumanMessage(content=content) if m["role"] == "user"
                            else AIMessage(content=content))
    _emit_pet("thinking")
    try:
        result = await asyncio.to_thread(
            call_llm, llm_messages, DEFAULT_CHAT_MODEL)
    except Exception as e:
        render_error(f"本地 LLM 调用失败: {str(e)[:200]}")
        _emit_pet("error")
        return ""
    if not result:
        render_error("本地 LLM 返回空（检查模型配置/API Key）")
        _emit_pet("error")
        return ""
    print(result)
    _emit_pet("idle")
    return result


async def run_query(mode: str, messages: list, on_approval=None) -> str:
    """按模式执行一轮；返回助手最终文本（空串 = 无产出/失败）"""
    history = messages[-MAX_SENT_MSGS:]
    if mode == "chat":
        return await run_chat_query(history)
    return await run_claude_query(history, on_approval=on_approval)


# ==================== REPL ====================

async def _ainput(prompt: str = "") -> str:
    line = await asyncio.get_running_loop().run_in_executor(None, input, prompt)
    return _clean_text(line).strip()


def _print_commands() -> None:
    print(f"{DIM}命令: /claude 本机Claude(默认)  /chat 本地LLM  /history 历史会话  "
          f"/clear 清空当前会话  /quit 退出{RESET}")


def _print_help(session: dict) -> None:
    mode = session.get("mode", "claude")
    print(f"{DIM}小元AI 终端对话 — 模式: {mode} | 会话: {session.get('id', '')} | "
          f"输入 /help 查看命令{RESET}")


async def _list_history(store: TerminalSessionStore) -> None:
    sessions = sorted(store._sessions.values(), key=lambda s: s.get("updated", 0), reverse=True)
    if not sessions:
        print(f"{DIM}(暂无历史会话){RESET}")
        return
    for s in sessions:
        first = next((m["content"][:30] for m in s.get("messages", []) if m["role"] == "user"), "(空会话)")
        print(f"{CYAN}{s['id']}{RESET}  {DIM}{s.get('mode', 'claude')}  "
              f"{len(s.get('messages', []))} 条  {time.strftime('%m-%d %H:%M', time.localtime(s.get('updated', 0)))}"
              f"{RESET}  {first}")


async def run_repl(session: dict, store: TerminalSessionStore) -> None:
    mode = session.get("mode", "claude")
    _print_help(session)
    while True:
        try:
            line = await _ainput(f"小元[{mode}]> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.startswith("/"):
            cmd = line.split(maxsplit=1)[0].lower()
            if cmd == "/quit":
                break
            elif cmd == "/clear":
                store.clear(session["id"])
                print(f"{DIM}当前会话已清空（{session['id']}）{RESET}")
            elif cmd == "/history":
                await _list_history(store)
            elif cmd == "/help":
                _print_commands()
            elif cmd == "/claude":
                mode = "claude"
                print(f"{DIM}已切换本机 Claude Code 模式{RESET}")
            elif cmd == "/chat":
                mode = "chat"
                print(f"{DIM}已切换本地 LLM 直连模式（{DEFAULT_CHAT_MODEL}）{RESET}")
            else:
                print(f"{DIM}未知命令: {cmd}（/help 查看）{RESET}")
            continue
        store.append(session["id"], "user", line, mode)
        result = await run_query(mode, session["messages"], on_approval=_approve_yn)
        if result.strip():
            store.append(session["id"], "assistant", result, mode)


async def run_pipe(query: str, mode: str) -> None:
    """管道模式：单轮输出、不落盘会话（脚本化场景）"""
    messages = [{"role": "user", "content": query}]
    await run_query(mode, messages, on_approval=_approve_yn)


def parse_args():
    p = argparse.ArgumentParser(description="小元AI 终端对话 CLI（默认 /claude 本机 Claude Code）")
    p.add_argument("--new", action="store_true", help="强制开新会话（默认自动续接上次会话）")
    p.add_argument("--session", default=None, help="续接指定会话 ID（/history 查看）")
    p.add_argument("--mode", default="claude", choices=["claude", "chat"],
                   help="启动模式：claude=本机 Claude Code（默认）/ chat=本地 LLM")
    return p.parse_args()


async def main():
    args = parse_args()
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
            print(f"{DIM}已续接上次会话 {session['id']}（{len(session['messages'])} 条历史；"
                  f"--new 开新会话）{RESET}")
    if session is None:
        session = store.new_session(args.mode)
    await run_repl(session, store)


if __name__ == "__main__":
    asyncio.run(main())
