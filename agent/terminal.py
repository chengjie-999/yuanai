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
# 而非真实仓库——选择链见 agent/cc_workspace.resolve_project_dir
# （CC_PROJECT_DIR > 数据根 cc_config.json > 源码根 / 内建 workspace）。
from agent.cc_workspace import resolve_project_dir  # noqa: E402

PROJECT_ROOT = resolve_project_dir()

SESSIONS_FILE = os.path.join(PROJECT_ROOT, "data", "terminal_sessions.json")
HISTORY_FILE = os.path.join(PROJECT_ROOT, "data", "terminal_history.txt")
DEFAULT_CHAT_MODEL = os.getenv("TERMINAL_CHAT_MODEL", "deepseek-flash")
MAX_TOOL_OUTPUT = 2000   # 终端回显工具输出截断（对齐 claude_bridge）
MAX_SESSIONS = 50        # 会话文件保留上限
MAX_STORED_MSGS = 200    # 每会话落盘消息上限（防文件无限增长）
MAX_SENT_MSGS = 100      # 每轮发送模型的历史上限（SDK 全量重发，必须封顶）
OBSERVE_PANEL_W = 34     # v3.2 #38 观测右栏宽度（右栏 + 左块网格并排）
OBSERVE_POLL_S = 15.0    # 观测轮询间隔（/chat/cc-activity，与网页同口径）
OBSERVE_STALE_S = 300    # 超此秒数无活动 = 黄条「可能已无响应」（与网页同语义）

# 桌宠六态 → 状态栏色点（v3.2 #38；与 pet_events 六态词一一对应）
PET_STATE_STYLE = {"thinking": "cyan", "working": "yellow", "attention": "magenta",
                   "error": "red", "idle": "green", "sleeping": "grey50"}

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

def _try_enable_vt() -> bool:
    """控制台 VT 自愈 + ANSI 能力探测（#13 2026-11-12，与 tray._enable_console_vt 同款）。

    GUI 程序 AllocConsole 自建的控制台默认不开启 VT 处理——ANSI 色码打出来是
    [90m 乱码、prompt_toolkit 控制台模式初始化失败。REPL 启动先尝试显式开启；
    返回 True = ANSI 可渲染（开启成功或本就有 VT）；False = 当前终端不解释 ANSI
    （非控制台句柄且 TERM 缺失/dumb），渲染层应强制无色。"""
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            h_out = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if not h_out or not kernel32.GetConsoleMode(h_out, ctypes.byref(mode)):
                # 非控制台句柄（mintty pty/管道）：ANSI 能力交给 TERM
                term = os.environ.get("TERM", "")
                return bool(term) and term != "dumb"
            ok = bool(mode.value & 0x0004)
            if not ok:
                ok = bool(kernel32.SetConsoleMode(h_out, mode.value | 0x0004))
            try:
                h_in = kernel32.GetStdHandle(-10)
                m2 = ctypes.c_uint32()
                if h_in and kernel32.GetConsoleMode(h_in, ctypes.byref(m2)) \
                        and not (m2.value & 0x0200):
                    kernel32.SetConsoleMode(h_in, m2.value | 0x0200)
            except Exception:
                pass
            return ok
        except Exception:
            return False
    term = os.environ.get("TERM", "")
    return bool(term) and term != "dumb"


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


def web_chat_url() -> str:
    """网站对话入口地址（终端状态栏/命令用，2026-11-12 用户诉求）：
    WEB_CHAT_URL 环境变量优先；否则从身份文件 server_url 推导——
    本地联调（localhost/ws://）指前端 5173，生产默认 https://cjyuanai.cn/chat。"""
    env = os.getenv("WEB_CHAT_URL")
    if env:
        return env
    url = "https://cjyuanai.cn/chat"
    try:
        from agent.main import load_identity
        su = (load_identity() or {}).get("server_url", "") or ""
        if "localhost" in su or "127.0.0.1" in su:
            url = "http://localhost:5173/chat"
    except Exception:
        pass
    return url


def _panel_url() -> str:
    """设置面板运行中 URL（panel.py 启动时落盘 data/panel_url.json；终端
    /panel 命令读此文件直达面板，2026-11-12）。未运行返回空串。"""
    try:
        from utils.data_path import root_path
        p = os.path.join(root_path(), "data", "panel_url.json")
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                return str((json.load(f) or {}).get("url", "") or "")
    except Exception:
        pass
    return ""


def _open_web_chat() -> str:
    """打开网站对话（浏览器新标签）；返回 URL。F2 快捷键与 /web 命令共用
    （2026-11-12 用户诉求：网站对话入口写进终端界面）。"""
    import threading
    import webbrowser
    url = web_chat_url()
    threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    return url


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
    """管道/测试渲染：纯文本直接打 stdout（capsys 可断言）。

    use_ansi=None → 跟随 _TTY（管道静默色码）；use_ansi=False → 强制无色
    （#13 2026-11-12：isatty 为真但终端不解释 ANSI 的场景——AllocConsole 自建
    控制台未开 VT 时 GRAY 常量带码会打 [90m 乱码）；True → 强制带码（测试用）。"""

    def __init__(self, use_ansi: bool = None):
        self._ansi = _TTY if use_ansi is None else use_ansi

    def _c(self, code: str) -> str:
        return code if self._ansi else ""

    def token(self, text: str) -> None:
        print(text, end="", flush=True)

    def reasoning(self, text: str) -> None:
        if not self._ansi:
            return  # 管道模式：思考内容不外泄（脚本消费者只要答案）
        print(f"{self._c(GRAY)}{text}{self._c(RESET)}", end="", flush=True)

    def tool_start(self, name: str) -> None:
        print(f"\n{self._c(CYAN)}⚙ {name}{self._c(RESET)}", flush=True)

    def tool_end(self, name: str, output: str) -> None:
        out = output if len(output) <= MAX_TOOL_OUTPUT else output[:MAX_TOOL_OUTPUT] + "\n...(输出过长已截断)"
        print(f"{self._c(GRAY)}{out}{self._c(RESET)}", flush=True)

    def done(self) -> None:
        print(flush=True)

    def error(self, text: str) -> None:
        print(f"\n{self._c(RED)}✗ {text}{self._c(RESET)}", flush=True)

    def info(self, text: str) -> None:
        print(f"{self._c(GRAY)}{text}{self._c(RESET)}", flush=True)

    def interrupted(self) -> None:
        print(f"\n{self._c(YELLOW)}（已停止生成）{self._c(RESET)}", flush=True)


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


# ==================== v3.0 全屏三区渲染（2026-11-12 #36） ====================

_REFRESH = object()  # ptk keybinding 触发的「重绘后重新进入输入」哨兵（run_repl 消费）


class FullscreenRenderer:
    """终端 TUI v3.0：状态栏（header）+ 对话流块（body）+ prompt_toolkit 输入 dock。

    - 对话以「块」持久化：answer（Markdown）/ thinking（折叠块「▸ 思考 (Xs) ·
      N 次工具调用」）/ tool（紧凑行「▸ ⚙ 工具名」，展开看输出截断）/ info / error
    - 流式：Live 原地刷新（非 alt-screen，与 ptk 输入互不打架），每帧 = 状态栏 +
      已有块 + 当前思考 + 流式回答（带光标 ▍）
    - 空闲：redraw() 清屏重打 状态栏 + 块（按 scroll_blocks 滚动窗口 + 折叠/选中
      态渲染），光标落底由 ptk 输入 dock 接续；keybinding（↑↓ 选择 / Enter 展开
      折叠 / PgUp PgDn 滚动 / Esc 取消）改状态后以 _REFRESH 哨兵退出 prompt，
      run_repl 重绘后重新进入（pending_input 保留未提交输入）
    - 接口与 Plain/RichRenderer 对齐（token/reasoning/tool_start/tool_end/done/
      error/info/interrupted），另加 set_mode/set_session/redraw/pending_input
    """

    def __init__(self, console=None, status_provider=None, cwd: str = "",
                 session_id: str = ""):
        from rich.console import Console
        self._console = console or Console()
        self._status_provider = status_provider  # callable → WS 状态词或 None
        self._cwd = cwd
        self._session_id = session_id
        self._mode = "claude"
        self._backend = ""      # 执行后端（local=本机统筹/cloud=云端，v3.1 backend_event 驱动）
        self._blocks: list[dict] = []   # kind/title/content/folded
        self._answer = ""       # 流式回答累积
        self._reasoning = ""    # 流式思考累积
        self._think_start = None
        self._tool_count = 0
        self._working = None    # 执行中的工具名
        self._live = None
        self.sel = None         # 选中块下标（blocks 内绝对下标）
        self.scroll_blocks = 0  # 从尾部隐藏的块数（PgUp 回看）
        self.pending_input = ""  # 折叠/滚动刷新时保留的输入缓冲
        # v3.2 #38 观测右栏：轮询线程只写状态（tick_observation），渲染时机
        # = Live 流式帧 / 非输入态整屏重绘（_prompt_active 时不动屏幕防与
        # ptk 输入行打架——工具栏 mini 状态线由 ptk 自身刷新兜底实时性）
        self._observe = None       # {"online", "age_s", "activities"} / {"error": True}
        self._observe_ready = False  # 云端通道客户端可用才渲染右栏
        self._usage = None         # {"total", "cached"} 上轮 token 消耗（usage_event）
        self._plan_view = None     # /plan 全屏视图（None=对话流；Esc/Enter 返回）
        self._prompt_active = False  # 输入等待中（run_repl 维护，轮询线程读）
        try:
            dark = os.getenv("TERMINAL_DARK", "1") == "1"
        except Exception:
            dark = True
        self._code_theme = "github-dark" if dark else "github-light"

    # ———— 状态栏 ————

    def set_mode(self, mode: str) -> None:
        self._mode = mode

    def set_session(self, session_id: str) -> None:
        self._session_id = session_id

    def set_backend(self, backend: str) -> None:
        """执行后端（v3.1 #37）：backend_event 驱动——local=本机统筹执行 /
        cloud=云端执行；状态栏可见（云边协同透明化）"""
        self._backend = "local" if backend == "local" else "cloud" if backend == "cloud" else ""

    def load_history(self, messages: list) -> None:
        """云端会话历史 → 块（v3.1 /sessions 切换与 /chat 进入时用）：
        user → 「你 ▸」块、assistant → answer 块；其余（META/system/tool）跳过"""
        self._blocks.clear()
        for m in messages or []:
            if not isinstance(m, dict):
                continue
            role = m.get("role", "")
            content = str(m.get("content", "") or "").strip()
            if not content:
                continue
            if role == "user":
                self._blocks.append({"kind": "user", "title": "", "content": content,
                                     "folded": False})
            elif role == "assistant":
                self._blocks.append({"kind": "answer", "title": "", "content": content,
                                     "folded": False})
        self.scroll_blocks = 0
        self.sel = None

    def _agent_dot(self):
        """本机 Agent 在线点：(文本, 样式)。Text.assemble 不解析 markup——
        直接给样式（#38 顺手修复 v3.0 状态栏字面 [green] 标签显示 bug）"""
        st = self._status_provider() if self._status_provider else None
        return {"online": ("● 在线", "green"),
                "connecting": ("● 连接中", "yellow"),
                "reconnecting": ("● 重连中", "yellow"),
                "offline": ("○ 离线", "grey50"),
                None: ("○ 离线", "grey50")}[st if st in (
                    "online", "connecting", "reconnecting", "offline") else None]

    def _header(self):
        from rich.text import Text
        dot, dot_style = self._agent_dot()
        pet = ""
        pet_style = "magenta"
        try:
            from agent.pet_events import last_state
            st = last_state()
            if st:
                pet = st
                pet_style = PET_STATE_STYLE.get(st, "magenta")
        except Exception:
            pass
        if pet:
            # v3.2 #38：桌宠六态色点（working 黄/error 红/idle 绿/thinking 青/
            # attention 紫/sleeping 灰空心）——一眼看电脑在干什么
            pet = f"{'○' if pet == 'sleeping' else '●'} 宠:{pet}"
        cwd = self._cwd
        if len(cwd) > 42:
            cwd = "…" + cwd[-41:]
        backend = {"local": "本机执行", "cloud": "云端执行"}.get(self._backend, "")
        return Text.assemble(
            (dot, dot_style), ("  ", ""),
            (self._mode, "bold cyan"),
            ("  ", ""), (backend, "green" if self._backend == "local" else "yellow"),
            ("  ", ""), (cwd or "—", "dim"), ("  ", ""),
            (f"会话 {self._session_id[:8]}" if self._session_id else "", "dim"),
            ("  ", ""), (pet, pet_style), ("  ", ""),
            ("F2 网站对话", "bright_black"), ("  ", ""),
            ("? 帮助", "bright_black"),
        )

    # ———— 块渲染 ————

    def _visible_blocks(self) -> list[tuple]:
        """滚动窗口：scroll_blocks=0 显示全部（跟随最新）；>0 隐藏尾部 N 块回看"""
        blocks = self._blocks
        if self.scroll_blocks > 0:
            blocks = blocks[:-self.scroll_blocks] if self.scroll_blocks < len(blocks) else []
        return [(i, b) for i, b in enumerate(blocks)]

    @staticmethod
    def _block_renderable(idx: int, b: dict, sel: int = None):
        """块 → rich 渲染对象。thinking/tool 折叠只出一行标题；选中块反色高亮"""
        from rich.text import Text
        from rich.markdown import Markdown
        from rich.console import Group
        kind = b.get("kind", "")
        folded = b.get("folded", False)
        if kind == "answer":
            return Markdown(b.get("content", ""))
        if kind == "user":
            return Text(f"你 ▸ {b.get('content', '')}", style="bold cyan")
        if kind == "info":
            return Text(b.get("content", ""), style="dim")
        if kind == "error":
            return Text(f"✗ {b.get('content', '')}", style="bold red")
        arrow = "▸" if folded else "▾"
        style = "reverse" if idx == sel else ("bold" if kind == "tool" else "dim")
        title = Text(f"{arrow} {b.get('title', '')}", style=style)
        if folded:
            return title
        return Group(title, Text(b.get("content", ""), style="dim"))

    # ———— v3.2 #38 观测右栏（执行观测面，愿景「手机看电脑在干什么」桌面侧） ————

    def set_usage(self, total: int, cached: int = 0) -> None:
        """上轮 token 消耗（usage_event，run_cloud_query 消费）"""
        self._usage = {"total": int(total or 0), "cached": int(cached or 0)}

    def tick_observation(self, data: dict) -> None:
        """轮询线程注入观测数据（15s /chat/cc-activity）：只更新状态；重绘仅在
        安全时机——Live 流式中逐帧更新（rich Live 锁线程安全）/ 非输入态整屏
        redraw（Console 写锁串行）。ptk 输入等待中不动屏幕，工具栏 mini 状态线
        由 ptk 自身刷新（refresh_interval）兜底实时性。"""
        self._observe = data or None
        if self._live is not None:
            self._refresh()
        elif not self._prompt_active:
            self.redraw()

    def _observe_panel(self):
        """右栏面板：状态色点（活跃绿/空闲黄/无响应黄条/离线灰）+ 最近 5 条
        活动（message + 多久前）+ 上轮 token 消耗。固定宽度 OBSERVE_PANEL_W。"""
        from rich.panel import Panel
        from rich.text import Text
        from rich.console import Group
        ob = self._observe
        lines = []
        if ob is None:
            lines.append(Text("连接云端…", style="dim"))
        elif ob.get("error"):
            lines.append(Text("云端不可用", style="bold red"))
            lines.append(Text("请检查设备绑定/网络", style="dim"))
        else:
            online = bool(ob.get("online"))
            age = ob.get("age_s")
            if not online:
                lines.append(Text("○ 离线", style="bold grey50"))
            elif age is None:
                lines.append(Text("● 在线 · 无活动记录", style="green"))
            elif age <= 60:
                lines.append(Text(f"● 活跃 · {int(age)}s 前", style="bold green"))
            elif age <= OBSERVE_STALE_S:
                lines.append(Text(f"● 空闲 · {int(age // 60)} 分钟", style="bold yellow"))
            else:
                lines.append(Text(f"● 已 {int(age // 60)} 分钟无活动", style="bold yellow"))
                lines.append(Text("可能已无响应（网页同提示）", style="yellow"))
            for a in (ob.get("activities") or [])[:5]:
                msg = str(a.get("message", "") or "").strip()[:22] or "活动"
                ago = ""
                ts = a.get("ts")
                if isinstance(ts, (int, float)):
                    s = max(0, int(time.time() - float(ts)))
                    ago = f"{s}s" if s < 60 else f"{s // 60}m" if s < 3600 else f"{s // 3600}h"
                lines.append(Text(f"• {msg}" + (f" {ago}" if ago else "")))
        if self._usage:
            lines.append(Text(f"上轮 {self._usage['total']} tokens"
                              + (f" · 缓存 {self._usage['cached']}" if self._usage["cached"] else ""),
                              style="dim"))
        return Panel(Group(*lines), title="执行观测", width=OBSERVE_PANEL_W,
                     padding=(0, 1))

    def _body(self, parts: list):
        """块流 + 观测右栏并排（grid 表固定两列：左列弹性 = 全宽−右栏，右栏
        固定 OBSERVE_PANEL_W）。宽终端（≥72）且云端通道可用才挂右栏；窄终端/
        无身份 → 纯块流全宽（降级不报错）。"""
        from rich.console import Group
        width = self._console.width or 80
        if not (self._observe_ready and width >= 72):
            return Group(*parts)
        from rich.table import Table
        grid = Table.grid(padding=(0, 0), pad_edge=False, collapse_padding=True)
        grid.add_column(width=width - OBSERVE_PANEL_W)
        grid.add_column(width=OBSERVE_PANEL_W)
        grid.add_row(Group(*parts), self._observe_panel())
        return grid

    # ———— v3.2 #38 /plan 全屏队列视图（Esc/Enter 返回对话流） ————

    def set_plan_view(self, data) -> None:
        """None = 退出计划视图（回到对话流块）"""
        self._plan_view = data

    def show_plans(self, plans: list, detail: dict = None) -> None:
        """计划列表（plans=卡列表）或单计划详情（detail=含 steps）进全屏视图"""
        self._plan_view = {"plans": plans or [], "detail": detail}
        self.sel = None
        self.scroll_blocks = 0

    def _plan_renderable(self):
        """计划队列渲染：列表=每计划状态词 + 进度条（rich ProgressBar 列）；
        详情=步骤逐行（状态标记/描述/运行中百分比/失败错误）。"""
        from rich.progress_bar import ProgressBar
        from rich.columns import Columns
        from rich.text import Text
        from rich.console import Group
        st_word = {"queued": "排队中", "running": "执行中", "done": "完成",
                   "failed": "失败", "draft": "草稿"}
        st_style = {"queued": "bold cyan", "running": "bold yellow",
                    "done": "bold green", "failed": "bold red", "draft": "dim"}
        head = self._plan_view
        parts = [Text("计划队列（/plan <序号> 查看步骤 · Esc/Enter 返回对话）",
                      style="bold underline")]
        detail = head.get("detail")
        if detail:
            steps = detail.get("steps") or []
            title = str(detail.get("title") or "(无标题)")[:40]
            st = str(detail.get("status") or "draft")
            prog = int(detail.get("progress") or 0)
            parts.append(Text.assemble(
                (f"▸ {title}  ", "bold"),
                (st_word.get(st, st), st_style.get(st, "dim")),
                ("  ", ""), (f"{prog}%", ""),
                (f"  {detail.get('done_steps', 0)}/{detail.get('total_steps', 0)} 步", "dim")))
            for s in steps:
                sst = str(s.get("status") or "pending")
                mark = {"running": "●", "done": "✔", "failed": "✗"}.get(sst, "○")
                mark_style = {"running": "yellow", "done": "green",
                              "failed": "red"}.get(sst, "dim")
                extra = ""
                if sst == "running":
                    extra = f" {int(s.get('progress') or 0)}%"
                err = f" {str(s.get('error') or '')[:40]}" if sst == "failed" and s.get("error") else ""
                parts.append(Text.assemble(
                    (f"  {mark} 第{s.get('step_no', '?')}步 ", mark_style),
                    (f"[{str(s.get('skill') or '-')}] ", "dim"),
                    (str(s.get("desc") or "")[:30], ""),
                    (extra, "yellow"), (err, "red")))
            return Group(*parts)
        plans = head.get("plans")
        if not plans:
            parts.append(Text("暂无计划——在网站对话中说「帮我制定…计划」，"
                              "创建后终端可直接看执行进度", style="dim"))
        for i, p in enumerate(plans):
            title = str(p.get("title") or "(无标题)")[:34]
            st = str(p.get("status") or "draft")
            prog = max(0, min(100, int(p.get("progress") or 0)))
            bar = ProgressBar(total=100, completed=prog, width=14,
                              complete_style="green", finished_style="green")
            parts.append(Group(
                Text.assemble((f"[{i + 1}] ", "bold"), (title, ""), ("  ", ""),
                              (st_word.get(st, st), st_style.get(st, "dim"))),
                Columns([bar,
                         Text.assemble((f"  {prog}%  ", ""),
                                       (f"{p.get('done_steps', 0)}/{p.get('total_steps', 0)} 步", "dim"),
                                       ("  ", ""), (str(p.get("message") or "")[:30], "dim"))],
                        padding=(0, 0), expand=False),
            ))
        return Group(*parts)

    # ———— 流式帧 ————

    def _refresh(self) -> None:
        from rich.live import Live
        from rich.markdown import Markdown
        from rich.text import Text
        from rich.console import Group
        if self._live is None:
            self._live = Live(Group(), console=self._console, refresh_per_second=12)
            self._live.start()
        parts = [self._header()]
        if self._plan_view is not None:
            parts.append(self._plan_renderable())
            self._live.update(Group(*parts))
            return
        for i, b in self._visible_blocks():
            parts.append(self._block_renderable(i, b, self.sel))
        if self._working:
            parts.append(Text(f"⚙ {self._working} 执行中…", style="bold yellow"))
        if self._reasoning:
            parts.append(Text("思考中…\n" + self._reasoning, style="dim italic"))
        parts.append(Markdown((self._answer or "…") + " ▍", code_theme=self._code_theme))
        self._live.update(self._body(parts))

    def _stop_live(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None

    def redraw(self) -> None:
        """空闲整屏重绘：清屏 → 状态栏 + 块（滚动/折叠/选中态；计划视图时替换
        为计划队列全宽；对话流观测右栏并排）。光标落底供 ptk。"""
        from rich.console import Group
        self._console.clear()
        parts = [self._header()]
        if self._plan_view is not None:
            parts.append(self._plan_renderable())
            self._console.print(Group(*parts))  # 计划视图全宽，不挂右栏
        else:
            for i, b in self._visible_blocks():
                parts.append(self._block_renderable(i, b, self.sel))
            self._console.print(self._body(parts))
        if self.sel is not None and self.sel >= len(self._blocks):
            self.sel = None

    # ———— 流式接口（与 Plain/RichRenderer 对齐） ————

    def _snapshot_thinking(self, final: bool = False) -> None:
        """当前累积思考落为折叠块（网页「思考快照挂工具卡上方」同语义）"""
        if not self._reasoning:
            return
        secs = int(time.time() - self._think_start) if self._think_start else 0
        title = (f"最终思考 ({secs}s)" if final else
                 f"思考 ({secs}s) · {self._tool_count} 次工具调用")
        self._blocks.append({"kind": "thinking", "title": title,
                             "content": self._reasoning, "folded": True})
        self._reasoning = ""
        self._think_start = None

    def token(self, text: str) -> None:
        if self._reasoning:  # 首个回答 token：剩余思考存为「最终思考」（网页同款）
            self._snapshot_thinking(final=True)
        self._answer += text
        self._refresh()

    def reasoning(self, text: str) -> None:
        if self._think_start is None:
            self._think_start = time.time()
        self._reasoning += text
        self._refresh()

    def tool_start(self, name: str) -> None:
        self._stop_live()
        self._tool_count += 1  # 先计数：思考块标题「N 次工具调用」含本次
        self._snapshot_thinking()
        self._working = name
        self._refresh()

    def tool_end(self, name: str, output: str) -> None:
        out = output if len(output) <= MAX_TOOL_OUTPUT else output[:MAX_TOOL_OUTPUT] + "\n...(输出过长已截断)"
        self._blocks.append({"kind": "tool", "title": f"⚙ {name}",
                             "content": out, "folded": True})
        self._working = None
        self.scroll_blocks = 0
        self._refresh()

    def done(self) -> None:
        self._stop_live()
        self._snapshot_thinking(final=True)
        if self._answer:
            self._blocks.append({"kind": "answer", "title": "",
                                 "content": self._answer, "folded": False})
            self._answer = ""
        self.scroll_blocks = 0
        self.redraw()

    def error(self, text: str) -> None:
        self._stop_live()
        self._blocks.append({"kind": "error", "title": "", "content": text,
                             "folded": False})
        self.scroll_blocks = 0
        self.redraw()

    def info(self, text: str) -> None:
        self._stop_live()
        self._blocks.append({"kind": "info", "title": "", "content": text,
                             "folded": False})
        self.redraw()

    def interrupted(self) -> None:
        self._stop_live()
        self._answer = ""
        self._blocks.append({"kind": "info", "title": "", "content": "（已停止生成）",
                             "folded": False})
        self.redraw()


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
    from agent.claude_loop import run_sdk_loop, load_credentials, endpoint_compliant, bridge_system_prompt

    render = render or PlainRenderer()
    api_key = load_credentials()
    if not api_key:
        render.error("未找到 Anthropic 凭证（ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / "
                     "~/.claude/.credentials.json）——请配置后重试，或 /chat 切本地 LLM")
        return ""
    # C9 出境开关（2026-10-29）：SDK 端点须显式指向合规网关
    if not endpoint_compliant():
        render.error("C9 出境开关：ANTHROPIC_BASE_URL 未设置或指向 Anthropic 官方端点，"
                     "已拒绝直连（数据出境）。请设置境内兼容网关（如 DeepSeek anthropic "
                     "端点）后重试，或 /chat 切本地 LLM")
        return ""

    _emit_pet("thinking")
    final = ""
    async for ev in run_sdk_loop(messages, api_key=api_key,
                                 system=bridge_system_prompt(),
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


# ==================== v3.1 云端对话通道（2026-11-12 #37：终端=第三端） ====================

def _make_cloud_client():
    """云端通道客户端（身份文件构造：agent_id + agent_secret + server_url）。
    无身份/未注册 → None（终端提示先去网页绑定设备）。"""
    try:
        from agent.main import load_identity
        from agent.chat_client import CloudChatClient
        identity = load_identity() or {}
        aid = identity.get("agent_id")
        secret = identity.get("agent_secret", "") or ""
        su = identity.get("server_url", "") or "wss://cjyuanai.cn"
        if not aid or not secret:
            return None
        return CloudChatClient(su, aid, secret)
    except Exception:
        return None


async def run_cloud_query(client, session_id: str, messages: list, render=None,
                          rich_mode: bool = False) -> str:
    """云端对话（v3.1）：/chat/stream SSE 与网站同链路——终端发的消息网站立即可见
    （多端第三端）。事件渲染复用 renderer 接口；approval 事件 → 终端内 Y/N
    （rich=ptk / plain=input），决议经 body.decision 回传云端（fail-closed）。"""
    render = render or PlainRenderer()
    loop = asyncio.get_running_loop()
    final = ""
    _emit_pet("thinking")
    try:
        async for ev in client.stream(session_id, messages[-1]["content"], messages[:-1]):
            t = ev.get("type", "")
            data = ev.get("data", {})
            if not isinstance(data, dict):
                data = {"text": str(data)}
            if t == "token":
                txt = str(data.get("text", ""))
                if txt:
                    final += txt
                    render.token(txt)
            elif t == "tool_start":
                name = str(data.get("name", "工具"))
                _emit_pet("working", tool=name)
                render.tool_start(name)
            elif t == "tool_end":
                name = str(data.get("name", "工具"))
                render.tool_end(name, _clean_text(str(data.get("output", "") or "")))
                _emit_pet("thinking")
            elif t == "backend_event":
                if isinstance(render, FullscreenRenderer):
                    render.set_backend(data.get("backend", ""))
            elif t == "approval":
                did = data.get("decision_id", "")
                tool_name = str(data.get("tool_name", "工具"))
                command = str(data.get("command", ""))[:200]
                render.info(f"⚠ 审批 [{tool_name}] {command}（120 秒超时默认拒绝）")
                _emit_pet("attention")
                if rich_mode:
                    ans = await _ptk_approve(tool_name, command)
                else:
                    ans = await loop.run_in_executor(
                        None, _approve_yn, did, tool_name, command)
                await loop.run_in_executor(
                    None, client.send_decision, did, ans == "approve")
                render.info("已同意执行" if ans == "approve" else "已拒绝")
                _emit_pet("working" if ans == "approve" else "thinking")
            elif t == "usage_event":
                # v3.2 #38：token 消耗进观测右栏（与网页消息脚注同口径）
                if isinstance(render, FullscreenRenderer):
                    render.set_usage(
                        (int(data.get("prompt_tokens") or 0)
                         + int(data.get("completion_tokens") or 0)),
                        int(data.get("cache_hit_tokens") or 0))
            elif t == "compliance_warning":
                render.info(_clean_text(str(data)))
            elif t == "error":
                render.error(_clean_text(str(data)))
                _emit_pet("error")
            elif t == "done":
                if not final:
                    final = _clean_text(str(data.get("display_content", "") or ""))
                render.done()
                _emit_pet("idle")
    except Exception as e:
        render.error(f"云端对话失败：{str(e)[:200]}")
        _emit_pet("error")
        return ""
    if not final:
        render.info("（本轮无文字回答）")
    return final


def _quiet_background_loggers() -> None:
    """REPL 全屏模式下静默后台线程噪音（真机 2026-11-12 报障）：yuan 同进程
    拉起 Agent——ws_client 重连/plan 执行器拉取的 warning 经 StreamHandler 打到
    stderr，与 ptk 输入行打架刷屏（本地后端没开时每几秒一行）。REPL 状态栏
    在线点与人话报错已自己呈现，warning 降 ERROR；data/logs/agent.log 文件
    仍全量留档可查。"""
    import logging
    for name in ("agent.ws_client", "agent.plan_executor", "agent.pet_events",
                 "agent.chat_client"):
        logging.getLogger(name).setLevel(logging.ERROR)


def _start_observe_poll(render, client_getter, interval: float = OBSERVE_POLL_S):
    """v3.2 #38 观测轮询：15s 拉 /chat/cc-activity → render.tick_observation
    （渲染时机由 tick 内安全判定）。失败静默——面板显示「云端不可用」，绝不阻塞
    对话；daemon 线程随进程退出。仅生产 ptk 路径启动（测试注入 prompt_fn 不启动，
    防真机身份文件触发真实网络）。"""
    import threading

    def _loop():
        while True:
            time.sleep(interval)
            try:
                client = client_getter()
                if client is None:
                    continue
                render.tick_observation(client.activity())
            except Exception:
                render.tick_observation({"error": True})

    threading.Thread(target=_loop, daemon=True, name="observe-poll").start()


# ==================== REPL（prompt_toolkit 企业级交互） ====================

async def _ainput(prompt: str = "") -> str:
    """纯文本模式输入（测试可 mock 的默认实现）"""
    line = await asyncio.get_running_loop().run_in_executor(None, input, prompt)
    return _clean_text(line).strip()


def _make_ptk_prompt(mode_ref, renderer=None) -> object:
    """prompt_toolkit PromptSession（惰性构造一次复用）：
    - 多行输入：Enter 提交 / Esc+Enter 换行——粘贴多行代码不碎行
    - FileHistory 跨会话历史（↑↓ 找回、左右编辑）
    - Ctrl+C → KeyboardInterrupt 冒泡（空闲退出/生成中停止）
    - renderer=FullscreenRenderer 时（v3.0 #36）：↑↓ 选块 / Enter 展开折叠 /
      PgUp PgDn 滚动 / Esc 取消——改状态后以 _REFRESH 哨兵退出，输入缓冲
      保留在 renderer.pending_input，run_repl 重绘后重新进入
    返回 prompt_fn = async () -> str | None | _REFRESH（None = EOF 退出）"""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.formatted_text import ANSI, HTML

    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        if renderer is not None and renderer._plan_view is not None:
            renderer.pending_input = event.current_buffer.text
            renderer.set_plan_view(None)
            event.app.exit(result=_REFRESH)
            return
        if renderer is not None and renderer.sel is not None:
            renderer.pending_input = event.current_buffer.text
            b = renderer._blocks[renderer.sel]
            if b.get("kind") in ("thinking", "tool"):
                b["folded"] = not b["folded"]
            event.app.exit(result=_REFRESH)
            return
        event.current_buffer.validate_and_handle()

    @kb.add("escape", "enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add("f2")
    def _(event):
        # 网站对话入口（2026-11-12 用户诉求：状态栏可见、一键直达浏览器）
        _open_web_chat()
        event.current_buffer.insert_text("")  # 不打断输入

    if renderer is not None:
        @kb.add("up")
        def _(event):
            if renderer._plan_view is not None:
                return  # 计划视图不参与块选择
            visible = renderer._visible_blocks()
            if not visible:
                return
            renderer.pending_input = event.current_buffer.text
            renderer.sel = visible[-1][0] if renderer.sel is None \
                else max(0, renderer.sel - 1)
            event.app.exit(result=_REFRESH)

        @kb.add("down")
        def _(event):
            if renderer._plan_view is not None:
                return
            visible = renderer._visible_blocks()
            if not visible:
                return
            renderer.pending_input = event.current_buffer.text
            last = visible[-1][0]
            renderer.sel = None if renderer.sel is None or renderer.sel >= last \
                else renderer.sel + 1
            event.app.exit(result=_REFRESH)

        @kb.add("escape")
        def _(event):
            if renderer._plan_view is not None:
                renderer.pending_input = event.current_buffer.text
                renderer.set_plan_view(None)
                event.app.exit(result=_REFRESH)
                return
            if renderer.sel is not None:
                renderer.pending_input = event.current_buffer.text
                renderer.sel = None
                event.app.exit(result=_REFRESH)

        @kb.add("pageup")
        def _(event):
            if renderer._plan_view is not None:
                return
            renderer.pending_input = event.current_buffer.text
            renderer.scroll_blocks += 5
            renderer.sel = None
            event.app.exit(result=_REFRESH)

        @kb.add("pagedown")
        def _(event):
            if renderer._plan_view is not None:
                return
            renderer.pending_input = event.current_buffer.text
            renderer.scroll_blocks = max(0, renderer.scroll_blocks - 5)
            event.app.exit(result=_REFRESH)

    # 斜杠命令补全（v3.1 #37）：仅对 "/" 开头的词弹候选（pattern 过滤，
    # 普通打字不打扰）
    from prompt_toolkit.completion import WordCompleter
    import re as _re
    session = PromptSession(
        multiline=True, key_bindings=kb,
        history=FileHistory(HISTORY_FILE),
        # Ctrl+R 反向历史搜索（v3.1 交互：ptk 内建，跨会话历史可搜）
        enable_history_search=True,
        # v3.2 #38：1s 刷新让工具栏 mini 观测线随 15s 轮询状态实时变化
        #（输入等待中不整屏重绘，ptk 自身重画工具栏是唯一的实时面）
        refresh_interval=1.0,
        completer=WordCompleter(
            ["/claude", "/chat", "/web", "/sessions", "/history", "/clear",
             "/quit", "/help", "/plan", "/status", "/panel", "/pet"],
            pattern=_re.compile(r"^/"), ignore_case=True),
    )

    def _toolbar():
        base = "↑↓ 选择 · Enter 展开/折叠 · PgUp/PgDn 滚动 · Esc+Enter 换行 · Ctrl+C 停止"
        if renderer is not None and renderer._plan_view is not None:
            return HTML("<b>计划视图</b> — Esc/Enter 返回对话流 | " + base)
        if renderer is not None and renderer.sel is not None:
            b = renderer._blocks[renderer.sel]
            return HTML(f"<b>已选中: {b.get('title', '')}</b> — Enter 展开/折叠 · Esc 取消 | {base}")
        # v3.2 #38 观测 mini 状态线：最近活动 + 多久前（有数据才占行）
        obs = renderer._observe if renderer is not None else None
        if obs and not obs.get("error") and obs.get("online") and obs.get("latest"):
            latest = obs["latest"]
            msg = str(latest.get("message", ""))[:24]
            age = obs.get("age_s")
            ago = ""
            if age is not None:
                s = max(0, int(age))
                ago = f"{s}s" if s < 60 else f"{s // 60}m" if s < 3600 else f"{s // 3600}h"
            color = "ansiyellow" if age is not None and age > 60 else "ansigreen"
            return HTML(f"<{color}>● {msg} {ago}</{color}> | <dim>{base}</dim>")
        return HTML(f"<dim>{base}</dim>")

    async def prompt_fn():
        try:
            mode = mode_ref[0]
            p = f"小元[{mode}]> " if mode != "claude" else "小元> "
            default = _ptk_default(renderer)
            if renderer is not None:
                renderer.pending_input = ""
            text = await session.prompt_async(ANSI(p), default=default,
                                              bottom_toolbar=_toolbar)
            if renderer is not None:
                renderer.pending_input = ""
            return text.strip()
        except EOFError:
            return None

    return prompt_fn


def _ptk_default(renderer) -> str:
    """输入默认值（_REFRESH 哨兵保留的未提交输入）。ptk 3.x 对 None 会
    TypeError（Document(None) → len(None)）——**永远返回 str**，绝不传 None
    （真机 2026-11-12 踩坑：VT 自愈后 ptk 首次真正工作，暴露该潜伏崩溃）。"""
    if renderer is None:
        return ""
    return renderer.pending_input or ""


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


def _print_plan_detail(render, detail: dict) -> None:
    """非全屏渲染的计划详情（纯文本回退）：步骤逐行"""
    st_word = {"queued": "排队中", "running": "执行中", "done": "完成",
               "failed": "失败", "draft": "草稿"}
    render.info(f"{str(detail.get('title') or '(无标题)')[:40]}  "
                f"{st_word.get(detail.get('status'), detail.get('status'))}  "
                f"{int(detail.get('progress') or 0)}%  "
                f"({detail.get('done_steps', 0)}/{detail.get('total_steps', 0)} 步)")
    for s in detail.get("steps") or []:
        extra = f" {int(s.get('progress') or 0)}%" if s.get("status") == "running" else ""
        err = f" {str(s.get('error') or '')[:40]}" if s.get("status") == "failed" else ""
        render.info(f"  第{s.get('step_no', '?')}步 [{s.get('skill', '-')}] "
                    f"{str(s.get('desc') or '')[:30]}{extra}{err}")


def _print_help(render) -> None:
    render.info("命令: /claude 本机Claude(默认)  /chat 云端对话(与网站同会话)  "
                "/sessions 网站会话  /web 网站对话  /plan 计划队列  /status 本机状态  "
                "/panel 设置面板  /pet on|off 桌宠  /history /clear /quit\n"
                "按键: F2 网站对话  Ctrl+R 搜索历史  ↑↓ 选择块  Enter 展开/折叠  "
                "PgUp/PgDn 滚动  Esc 取消  Esc+Enter 换行  Ctrl+C 停止生成\n"
                "v3.2: 右栏执行观测（15s 轮询最近活动）/ 计划视图 Esc 返回  "
                "/plan <序号> 看步骤进度")


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
    rich_mode = render is not None and isinstance(render, (RichRenderer, FullscreenRenderer))
    render = render or PlainRenderer()
    custom_prompt = prompt_fn is not None  # 测试注入标记（决定是否起观测轮询线程）
    # #13（2026-11-12）：VT 自愈先于 ptk 初始化——自建控制台补开 VT 后
    # prompt_toolkit 可能直接就绪；失败时再按 ANSI 能力降级渲染层
    ansi_ok = _try_enable_vt()
    if prompt_fn is None:
        if rich_mode:
            try:
                prompt_fn = _make_ptk_prompt(
                    mode_ref, render if isinstance(render, FullscreenRenderer) else None)
            except Exception:
                # 非标准 Windows 控制台（Git Bash mintty 未加 winpty / 自建控制台等）：
                # 交互层回退基础 input()；终端不解释 ANSI 时渲染层同步降级纯文本
                # （PlainRenderer use_ansi=False）——不再打 [90m 色码乱码；
                # ANSI 正常时全屏渲染器降回 v2 流式（交互增强不可用）
                if not ansi_ok:
                    render = PlainRenderer(use_ansi=False)
                elif isinstance(render, FullscreenRenderer):
                    render = RichRenderer()
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

    if isinstance(render, FullscreenRenderer):
        render.set_mode(mode)
        render.set_session(session.get("id", ""))
    else:
        render.info(f"小元AI 终端对话 — 模式: {mode} | 会话: {session.get('id', '')} | /help 查看命令")

    # v3.1 云端通道状态（/chat 进入后生效；/claude 保持本地草稿互不干扰）。
    # v3.2 #38：client 提前构造——观测右栏 /claude 模式也可用（CC 活动流），
    # 构造零网络（令牌懒取），无身份 → None（右栏不渲染，/chat 时提示绑定）
    cloud_client = _make_cloud_client()
    cloud_sid = ""
    cloud_messages: list = []
    if isinstance(render, FullscreenRenderer):
        render._observe_ready = cloud_client is not None
        if cloud_client is not None and not custom_prompt:
            _start_observe_poll(render, lambda: cloud_client)
        render.redraw()  # 启动即画状态栏+右栏（v3.0 遗留：此前要等首次按键才重绘）

    while True:
        if isinstance(render, FullscreenRenderer):
            render._prompt_active = True  # 输入等待中：轮询线程只更新状态不重绘
        try:
            line = await prompt_fn()
        except KeyboardInterrupt:
            # 空闲时 Ctrl+C = 退出
            print()
            break
        finally:
            if isinstance(render, FullscreenRenderer):
                render._prompt_active = False
        if line is None:
            break
        if line is _REFRESH:
            # 折叠/滚动/选择键：渲染器状态已变——重绘后重新进入输入（缓冲保留）
            if isinstance(render, FullscreenRenderer):
                render.redraw()
            continue
        line = line.strip()
        if not line:
            continue
        if isinstance(render, FullscreenRenderer) and render._plan_view is not None:
            render.set_plan_view(None)  # 任何输入退出计划视图（命令照常分发）
        if line.startswith("/"):
            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""
            if cmd == "/quit":
                break
            elif cmd == "/clear":
                store.clear(session["id"])
                if isinstance(render, FullscreenRenderer):
                    render._blocks.clear()  # 会话消息清空 → 渲染块同步清空
                if mode == "cloud":
                    render.info("云端会话以网站为准——/clear 仅清空终端显示，网站历史保留")
                else:
                    render.info(f"当前会话已清空（{session['id']}）")
            elif cmd == "/history":
                await _list_history(store, render)
            elif cmd == "/help":
                _print_help(render)
            elif cmd == "/claude":
                mode = "claude"; mode_ref[0] = mode
                if isinstance(render, FullscreenRenderer):
                    render.set_mode(mode)
                    render.set_session(session.get("id", ""))
                render.info("已切换本机 Claude Code 模式（本地专业模式）")
            elif cmd == "/chat":
                # v3.1：云端对话通道（终端=第三端，与网站同一会话体系；
                # 云端是小元AI 正身——本机统筹在线时云端自动与其协同）
                if cloud_client is None:
                    cloud_client = _make_cloud_client()
                if cloud_client is None:
                    render.error("未找到本机 Agent 身份（agent_identity.json）——"
                                 "请先在网页登录并完成设备绑定，再回终端 /chat")
                    continue
                try:
                    loop = asyncio.get_running_loop()
                    cloud_sid = await loop.run_in_executor(
                        None, cloud_client.main_session_id)
                    cloud_messages = await loop.run_in_executor(
                        None, cloud_client.load_messages, cloud_sid)
                except Exception as e:
                    render.error(f"连接云端对话失败：{str(e)[:160]}")
                    continue
                mode = "cloud"; mode_ref[0] = mode
                if isinstance(render, FullscreenRenderer):
                    render.set_mode(mode)
                    render.set_session(cloud_sid)
                    render.load_history(cloud_messages)
                    render.redraw()
                else:
                    render.info(f"已连接云端对话（主对话 {cloud_sid[:8]}，"
                                f"{len(cloud_messages)} 条历史）")
            elif cmd == "/sessions":
                # 网站会话列表/切换（多端同一批会话）
                if cloud_client is None:
                    cloud_client = _make_cloud_client()
                if cloud_client is None:
                    render.error("未找到本机 Agent 身份——请先在网页绑定设备")
                    continue
                try:
                    loop = asyncio.get_running_loop()
                    if arg and arg.isdigit():
                        sessions = await loop.run_in_executor(
                            None, cloud_client.list_sessions)
                        idx = int(arg) - 1
                        if not (0 <= idx < len(sessions)):
                            render.info(f"序号无效（1-{len(sessions)}）")
                            continue
                        cloud_sid = str(sessions[idx].get("session_id", ""))
                        cloud_messages = await loop.run_in_executor(
                            None, cloud_client.load_messages, cloud_sid)
                        mode = "cloud"; mode_ref[0] = mode
                        if isinstance(render, FullscreenRenderer):
                            render.set_mode(mode)
                            render.set_session(cloud_sid)
                            render.load_history(cloud_messages)
                            render.redraw()
                        else:
                            render.info(f"已切换到会话 {cloud_sid[:8]}"
                                        f"（{len(cloud_messages)} 条历史）")
                    else:
                        sessions = await loop.run_in_executor(
                            None, cloud_client.list_sessions)
                        for i, s in enumerate(sessions):
                            title = str(s.get("title") or "(无标题)")[:36]
                            mark = "★" if s.get("is_main") else " "
                            render.info(f"[{i + 1}]{mark} {title}  "
                                        f"{str(s.get('session_id', ''))[:8]}")
                        render.info("切换：/sessions <序号>；不传参=列表")
                except Exception as e:
                    render.error(f"会话列表获取失败：{str(e)[:160]}")
            elif cmd == "/status":
                from agent.pet_events import last_state
                st = None
                if isinstance(render, FullscreenRenderer) and render._status_provider:
                    st = render._status_provider()
                pet = last_state()
                render.info(f"本机 Agent：{st or '未运行'} ｜ 桌宠：{pet or '—'} ｜ "
                            f"云端通道：{'已连接' if cloud_client else '未连接'}")
            elif cmd == "/plan":
                # v3.2 #38 终端计划队列视图：与网站 /chat/plan 同列表（用户 JWT
                # 口径）；/plan <序号|id> 进单计划详情（步骤 + 进度）
                if cloud_client is None:
                    render.error("未找到本机 Agent 身份——请先在网页绑定设备")
                    continue
                loop = asyncio.get_running_loop()
                try:
                    plans = await loop.run_in_executor(None, cloud_client.list_plans)
                except Exception as e:
                    render.error(f"计划列表获取失败：{str(e)[:160]}")
                    continue
                if arg:
                    idx = int(arg) - 1 if arg.isdigit() else None
                    target = None
                    if idx is not None and 0 <= idx < len(plans):
                        target = plans[idx]
                    else:
                        for p in plans:
                            if str(p.get("id")) == arg:
                                target = p
                                break
                    if target is None:
                        render.info(f"计划不存在（列表 1-{len(plans)}）")
                        continue
                    try:
                        detail = await loop.run_in_executor(
                            None, cloud_client.plan_detail, target.get("id"))
                    except Exception as e:
                        render.error(f"计划详情获取失败：{str(e)[:160]}")
                        continue
                    if isinstance(render, FullscreenRenderer):
                        render.show_plans(plans, detail)
                        render.redraw()
                    else:
                        _print_plan_detail(render, detail)
                    continue
                if isinstance(render, FullscreenRenderer):
                    render.show_plans(plans)
                    render.redraw()
                else:
                    if not plans:
                        render.info("暂无计划——在网站对话中说「帮我制定…计划」创建")
                    for i, p in enumerate(plans):
                        st = str(p.get("status") or "draft")
                        render.info(f"[{i + 1}] {str(p.get('title') or '(无标题)')[:40]}  {st}  "
                                    f"{int(p.get('progress') or 0)}%  "
                                    f"({p.get('done_steps', 0)}/{p.get('total_steps', 0)} 步)")
                    render.info("详情：/plan <序号>")
            elif cmd == "/panel":
                # 设置面板入口：读面板进程落盘的 URL 文件（panel.py 启动时写）
                url = _panel_url()
                if url:
                    import threading
                    import webbrowser
                    threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
                    render.info(f"正在打开设置面板：{url}")
                else:
                    render.info("设置面板未运行——请从托盘菜单「打开设置面板…」进入")
            elif cmd == "/pet":
                from agent.pet_events import launch_pet, stop_pet
                want_on = arg.lower() not in ("off", "stop", "0")
                ok, msg = launch_pet() if want_on else stop_pet()
                render.info(msg)
            elif cmd == "/web":
                # 网站对话入口（2026-11-12 用户诉求，与状态栏 F2 同款）
                url = _open_web_chat()
                render.info(f"正在打开网站对话：{url}")
            else:
                render.info(f"未知命令: {cmd}（/help 查看）")
            continue
        if mode == "cloud":
            # 云端对话发送：消息落网站会话（/chat/save 同链路，多端互通）
            loop = asyncio.get_running_loop()
            cloud_messages.append({"role": "user", "content": line})
            task = asyncio.create_task(run_cloud_query(
                cloud_client, cloud_sid, cloud_messages, render=render,
                rich_mode=rich_mode))
            try:
                result = await task
            except KeyboardInterrupt:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
                render.interrupted()
                _emit_pet("idle")
                continue
            if result.strip():
                cloud_messages.append({"role": "assistant", "content": result})
            try:
                await loop.run_in_executor(
                    None, cloud_client.save_messages, cloud_sid, cloud_messages)
            except Exception as e:
                render.info(f"同步到网站失败：{str(e)[:120]}")
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
    p = argparse.ArgumentParser(description="小元AI 本地 Agent 终端（yuan：终端对话 + 云端联动一体）")
    p.add_argument("--new", action="store_true", help="强制开新会话（默认自动续接上次会话）")
    p.add_argument("--session", default=None, help="续接指定会话 ID（/history 查看）")
    p.add_argument("--mode", default="claude", choices=["claude", "chat"],
                   help="启动模式：claude=本机 Claude Code（默认）/ chat=本地 LLM")
    p.add_argument("-p", "--pipe", default=None,
                   help="管道单轮问答（claude -p 同款，不落盘会话）")
    p.add_argument("--install-yuan", action="store_true",
                   help="把 yuan/yuancc 装进用户 PATH（任何目录直接 yuan 启动）")
    # Agent 形态直通（yuan = 本地 Agent 的终端形态，2026-10-25 合一）：
    p.add_argument("--install", default=None, help="安装码：注册本机设备后退出")
    p.add_argument("--tray", action="store_true", help="托盘形态（无终端窗口，后台常驻）")
    p.add_argument("--server-url", default=None, help="云端 WebSocket 地址（默认身份文件/wss://cjyuanai.cn）")
    p.add_argument("--agent-name", default=None, help="Agent 显示名称")
    p.add_argument("--no-plan-executor", action="store_true", help="禁用计划执行器线程")
    p.add_argument("--no-agent", action="store_true",
                   help="REPL 不拉起后台 Agent（发布版 exe 内置终端用：托盘进程已持有"
                        "云端连接，再拉会双连互踢）")
    p.add_argument("--update", action="store_true",
                   help="下载云端默认版本的 Agent 安装包（sha256 校验后提示安装）")
    return p.parse_args()


def install_yuan_command() -> int:
    """把 `yuan` / `yuancc` 装进用户 PATH（仿 claude 命令，2026-10-25 用户拍板两入口）：
    - yuan   = 小元本地 Agent 的终端形态（终端对话 + 后台云端联动 + 桌宠一体；
               --install <码> 注册 / --tray 托盘 / -p 管道 / /chat 本地 LLM）
    - yuancc = Claude Code 原生终端（参数透传：yuancc -p "问题" = claude -p）
    ① 生成两个 .bat（内嵌仓库路径 + venv python，ASCII 内容防 cmd GBK 误读）
       到 %LOCALAPPDATA%\\yuan\\
    ② 清理旧版三入口残留（yuanagent.bat 已并入 yuan）
    ③ 该目录追加进用户 PATH（PowerShell 用户级写回，防 setx 1024 截断；幂等）"""
    import subprocess
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    inst_dir = os.path.join(local, "yuan")
    os.makedirs(inst_dir, exist_ok=True)

    yuan_bat = os.path.join(inst_dir, "yuan.bat")
    with open(yuan_bat, "w", encoding="ascii") as f:
        f.write('@echo off\n')
        f.write('rem XiaoYuanAI local agent terminal (installed by --install-yuan)\n')
        f.write(f'cd /d "{repo}"\n')
        f.write('venv\\Scripts\\python.exe -m agent.terminal %*\n')
        f.write('exit /b %errorlevel%\n')

    # 三入口合一后的旧命令清理（yuanagent 已并入 yuan --install/--tray）
    old_agent_bat = os.path.join(inst_dir, "yuanagent.bat")
    if os.path.exists(old_agent_bat):
        try:
            os.remove(old_agent_bat)
        except OSError:
            pass

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
    print(f"✅ yuan / yuancc 已安装到: {inst_dir}")
    print("   新开一个终端窗口即可使用：")
    print("   yuan    = 本地 Agent 终端（对话 + 云端联动 + 桌宠一体）")
    print("   yuancc  = Claude Code 原生终端（yuancc -p \"问题\" 管道单轮）")
    print("   注册/托盘：yuan --install <安装码> / yuan --tray")
    print("   下载更新：yuan --update（下载云端默认版本安装包）")
    return 0


def cmd_update() -> int:
    """yuan --update（2026-10-30）：下载云端默认版本安装包到更新目录，
    sha256 同步校验（fail-closed），一致后提示双击安装（不搞自替换）。"""
    import hashlib
    import json as _json
    import urllib.request
    from agent.main import load_identity

    identity = load_identity() or {}
    server = str(identity.get("server_url", "") or "")
    if not server:
        server = os.getenv("YUAN_SERVER_URL", "")
    base = server.strip().rstrip("/")
    if base.startswith("wss://"):
        base = "https://" + base[len("wss://"):]
    elif base.startswith("ws://"):
        base = "http://" + base[len("ws://"):]
    if not base.startswith(("https://", "http://")):
        base = "https://cjyuanai.cn"
    # 护栏：远程明文一律拒绝（localhost 豁免）
    if base.startswith("http://") and "localhost" not in base and "127.0.0.1" not in base:
        print("yuan --update 必须走 https（远程明文下载已拒绝）；本地联调可用 localhost")
        return 1

    try:
        with urllib.request.urlopen(f"{base}/downloads/version.json", timeout=10) as resp:
            manifest = _json.loads(resp.read().decode("utf-8"))
        remote_sha = str(manifest.get("sha256", "")).lower()
        if not remote_sha:
            print("云端清单缺少 sha256，已拒绝下载（fail-closed）")
            return 1
        exe_url = f"{base}{manifest.get('exe', '/downloads/yuanai-agent.exe')}"
        version = str(manifest.get("version", ""))

        # 落盘目录：frozen → %LOCALAPPDATA%\XiaoYuanAI\update；源码 → data/update
        if getattr(sys, "frozen", False):
            out_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                                   "XiaoYuanAI", "update")
        else:
            from utils.data_path import root_path
            out_dir = os.path.join(root_path(), "data", "update")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"yuanai-agent-v{version}.exe")  # 统一命名规范（2026-10-30）

        print(f"正在下载 v{version}（{manifest.get('size', 0) // (1024 * 1024)}MB）...")
        hasher = hashlib.sha256()
        tmp = out_path + ".downloading"
        with urllib.request.urlopen(exe_url, timeout=300) as resp, open(tmp, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
                f.write(chunk)
        if hasher.hexdigest().lower() != remote_sha:
            os.remove(tmp)
            print("sha256 校验失败，已删除下载文件（安全拒绝）")
            return 1
        os.replace(tmp, out_path)
        print(f"下载完成：{out_path}")
        print("请双击该安装包完成升级（新 exe 自带安装引导，会迁移旧数据）。")
        return 0
    except Exception as e:
        print(f"下载失败: {str(e)[:200]}")
        return 1


async def main():
    args = parse_args()
    if args.install_yuan:
        sys.exit(install_yuan_command())
    if args.update:
        sys.exit(cmd_update())

    # —— Agent 形态直通（yuan = 本地 Agent 的终端形态，与 agent.main 同入口）——
    if args.install:
        from agent.main import do_install
        do_install(args.server_url or "wss://cjyuanai.cn", args.install)
        return
    if args.tray:
        from agent.tray import main as tray_main
        tray_main()
        return

    # -p 管道单轮（claude -p 同款）：轻量单轮，不起 Agent、不落盘会话
    if args.pipe:
        await run_pipe(args.pipe, args.mode)
        return

    store = TerminalSessionStore()
    store.load()

    if not sys.stdin.isatty():
        # 管道模式：echo "问题" | python -m agent.terminal（单轮轻量，不起 Agent）
        query = read_stdin_query()
        if not query:
            print("用法: echo \"问题\" | python -m agent.terminal", file=sys.stderr)
            return
        await run_pipe(query, args.mode)
        return

    # #13（2026-11-12）：终端不解释 ANSI 时，REPL 前后的提示行也强制无色——
    # 模块级色码常量在 import 时按 isatty 固化，此处补 ANSI 能力判断清零
    # （「已续接上次会话」等 main 层打印不再打 [90m 乱码）
    if not _try_enable_vt():
        global GRAY, CYAN, YELLOW, RED, RESET
        GRAY = CYAN = YELLOW = RED = RESET = ""

    # REPL 模式：同进程拉起后台 Agent（云端联动 + 计划执行 + 桌宠事件）——
    # 无身份文件时静默跳过（纯本地终端）；远端 ws:// 被护栏拒绝仅提示不阻塞终端；
    # --no-agent（发布版 exe 内置终端）：托盘进程已持有云端连接，跳过防双连互踢
    _quiet_background_loggers()
    handle = None
    try:
        from agent.main import load_identity, run_agent
        identity = load_identity()
        if identity.get("agent_id") and not args.no_agent:
            handle = await run_agent(
                server_url=args.server_url or identity.get("server_url") or "wss://cjyuanai.cn",
                agent_id=str(identity.get("agent_id")),
                agent_token=identity.get("agent_secret", "") or "",
                agent_name=args.agent_name or "小元AI 本地 Agent",
                no_plan_executor=args.no_plan_executor,
            )
    except SystemExit as e:
        print(f"{YELLOW}{e}{RESET}", file=sys.stderr)
    except Exception as e:
        print(f"{GRAY}云端联动启动失败（终端功能不受影响）: {str(e)[:120]}{RESET}", file=sys.stderr)

    try:
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

        # v3.0 全屏三区（#36 2026-11-12）：状态栏在线点数据源 = 进程内 Agent 连接
        # 状态（--no-agent 发布版形态 handle=None → 离线点，v3.1 起云端轮询补齐）
        cwd = ""
        try:
            from agent.cc_workspace import resolve_project_dir
            cwd = resolve_project_dir() or ""
        except Exception:
            pass

        def _agent_status():
            return handle.status if handle else None

        await run_repl(session, store, render=FullscreenRenderer(
            cwd=cwd, session_id=session.get("id", ""),
            status_provider=_agent_status))
    finally:
        if handle:
            await handle.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
