"""终端 TUI v4：Textual 渲染层（2026-11-15 拍板，决策点 A；方案
plans/terminal-renderer-textual-2026-11.md）。

用户实测痛点（v3 rich 全帧重绘）：「消息步骤太多，固定顶栏不牢、画面抽搐、
鼠标不能滑动」。选型回答：不换 JS（拆进程重写全终端）——Python 界 CC 对应物
= Textual：widget 组件树 + **diff 渲染（只重绘变化 widget，token 流只更新
流式回答一个 Markdown）** + 原生鼠标滚轮 + 固定 Header/输入 dock + alt-screen
自动进出（scrollback 不残留）。

复用边界（与方案一致，重写面收敛）：
- chat_client / claude_loop / 审批决议 / 计划客户端 / 观测轮询线程 / pet_events
  / 会话存储 / web_chat_url / cc_workspace 全复用零改动
- 命令分发与回合执行 = terminal.dispatch_command / run_turn（与 v3 ptk 共用
  同一份逻辑——ReplContext 单一行为事实源）
- 本模块只重写：渲染器（FullscreenRenderer → TextualRenderer）+ 交互循环
  （ptk prompt/_REFRESH 哨兵 → Textual App 事件循环，审批 Y/N → App 内 modal）
- 降级链保留：textual 未装/启动失败 → 回退 v3 全屏 ptk（terminal.run_repl 内）

本模块顶层 import textual——所有引用方（terminal.main / run_repl / 测试）都
经 try/except 懒加载，本地 Agent 零硬依赖。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import re
import threading
import time
import uuid

from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Markdown, ProgressBar, Static, TextArea

from agent.terminal import (  # terminal 懒加载本模块，反向引用安全
    HISTORY_FILE,
    MAX_TOOL_OUTPUT,
    OBSERVE_PANEL_W,
    OBSERVE_STALE_S,
    PLAN_ST_STYLE,
    PLAN_ST_WORD,
    ReplContext,
    _emit_pet,
    _header_text,
    _observe_lines,
    dispatch_command,
    run_turn,
)

# 斜杠命令补全清单（与 v3 ptk WordCompleter 同口径）
_COMMANDS = ["/claude", "/chat", "/web", "/sessions", "/history", "/clear",
             "/quit", "/help", "/plan", "/status", "/panel", "/pet"]

# 流式回答 Markdown 刷新节流（秒）：Markdown 解析是同步重活，每 token 全解析
# 会吃掉 diff 渲染省下的预算——80ms 窗口内 token 累积、到点一次刷新
STREAM_FLUSH_INTERVAL = 0.08

_HINT_BASE = "↑↓ 选择 · Enter 展开/折叠 · PgUp/PgDn 滚动 · Esc+Enter 换行 · Ctrl+C 停止 · ? 帮助"


class BlockWidget(Vertical):
    """对话块容器：answer=Markdown（富文本）、user/info/error=Static、thinking/
    tool=折叠块（标题行 + 展开时内容行）。folded 切换 = 内容子件挂载/卸载
    （in-place 改，不重建 widget、不丢滚动位置）。选中态 .selected 由 app 同步。"""

    def __init__(self, bid: str, kind: str, title: str, content: str, folded: bool):
        super().__init__(classes="block")
        self.bid = bid
        self.block_kind = kind
        self.block_title = title
        self.block_content = content
        self.block_folded = bool(folded)

    def compose(self):
        kind = self.block_kind
        if kind == "answer":
            yield Markdown(self.block_content or "（空）", classes="banswer")
        elif kind == "user":
            yield Static(Text(f"你 ▸ {self.block_content}", style="bold cyan"))
        elif kind == "info":
            yield Static(Text(self.block_content, style="dim"))
        elif kind == "error":
            yield Static(Text(f"✗ {self.block_content}", style="bold red"))
        else:  # thinking / tool 折叠块
            yield Static(self._title_text(), classes="btitle")
            if not self.block_folded:
                yield Static(Text(self.block_content, style="dim"), classes="bcontent")

    def _title_text(self) -> Text:
        arrow = "▸" if self.block_folded else "▾"
        style = "bold" if self.block_kind == "tool" else "dim"
        return Text(f"{arrow} {self.block_title}", style=style)

    def set_folded(self, folded: bool) -> None:
        """折叠/展开（v3 Enter 语义）：标题箭头翻转 + 内容行挂/卸"""
        if folded == self.block_folded:
            return
        self.block_folded = folded
        self.query(".btitle", Static).first().update(self._title_text())
        if folded:
            for c in self.query(".bcontent"):
                c.remove()
        else:
            self.mount(Static(Text(self.block_content, style="dim"), classes="bcontent"))

    def on_click(self, event) -> None:
        """P1 鼠标交互：点击折叠块标题行 = 展开/折叠（Textual 原生滚轮/滚动条
        拖拽已覆盖其余鼠标诉求）。仅在标题行生效——展开态点内容不干扰"""
        if self.block_kind not in ("thinking", "tool"):
            return
        if "btitle" not in getattr(event.widget, "classes", set()):
            return
        render = self.app.renderer
        for i, b in enumerate(render._blocks):
            if b.get("bid") == self.bid:
                render.toggle_fold(i)
                break


class SubmitLine(Message):
    """输入 dock 提交一条消息（命令或对话文本；提交后输入框已清空）"""

    def __init__(self, line: str):
        super().__init__()
        self.line = line


class DockInput(TextArea):
    """输入 dock：Enter 提交（计划视图退出/选中块折叠优先；生成中忽略）、
    Esc+Enter 换行、↑↓ 块选择、PgUp/PgDn 滚动、End 回到底部、Tab 斜杠命令
    补全。v3 ptk 交互语义不动（#36 键盘契约）。"""

    BINDINGS = [
        Binding("enter", "dock_enter", "提交", priority=True),
        Binding("escape", "dock_escape", "取消", priority=True),
        Binding("up", "dock_up", "上一块", priority=True),
        Binding("down", "dock_down", "下一块", priority=True),
        Binding("pageup", "dock_page_up", "上翻", priority=True),
        Binding("pagedown", "dock_page_down", "下翻", priority=True),
        Binding("end", "dock_end", "回到底部", priority=True),
        Binding("tab", "dock_complete", "补全", priority=True),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(show_line_numbers=False, *args, **kwargs)
        self._esc_armed = False  # Esc 后下一次 Enter = 换行（ptk escape+enter 同款）

    def on_mount(self) -> None:
        # 输入历史落盘（v3 ptk FileHistory 同源文件；Ctrl+R 搜索迁移 P2）
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8", errors="replace") as f:
                self._history = [ln.rstrip("\n") for ln in f if ln.strip()]
        except Exception:
            self._history = []

    def _remember(self, line: str) -> None:
        self._history.append(line)
        if len(self._history) > 500:
            self._history = self._history[-500:]
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(self._history) + "\n")
        except Exception:
            pass

    def action_dock_enter(self) -> None:
        app = self.app
        render = app.renderer
        if app.busy:
            return  # 生成中忽略提交（v3：流式期间 prompt 未恢复）
        if self._esc_armed:
            self._esc_armed = False
            self.insert("\n")
            return
        if render._plan_view is not None:
            render.set_plan_view(None)
            return
        if render.sel is not None:
            b = render._blocks[render.sel]
            if b.get("kind") in ("thinking", "tool"):
                render.toggle_fold(render.sel)
                return
        line = self.text
        self._remember(line)
        self.post_message(SubmitLine(line))
        self.clear()

    def action_dock_escape(self) -> None:
        app = self.app
        render = app.renderer
        if render._plan_view is not None:
            render.set_plan_view(None)
        elif render.sel is not None:
            render.sel = None
            render._notify()
        else:
            self._esc_armed = True
        app.sync_hint()

    def action_dock_up(self) -> None:
        app = self.app
        render = app.renderer
        if render._plan_view is not None:
            return
        blocks = render._blocks
        if not blocks:
            return
        render.sel = len(blocks) - 1 if render.sel is None else max(0, render.sel - 1)
        render._notify()
        app.sync_hint()

    def action_dock_down(self) -> None:
        app = self.app
        render = app.renderer
        if render._plan_view is not None:
            return
        blocks = render._blocks
        if not blocks:
            return
        last = len(blocks) - 1
        render.sel = None if render.sel is None or render.sel >= last else render.sel + 1
        render._notify()
        app.sync_hint()

    def action_dock_page_up(self) -> None:
        self.app._blocks_container.scroll_page_up()

    def action_dock_page_down(self) -> None:
        self.app._blocks_container.scroll_page_down()

    def action_dock_end(self) -> None:
        self.app._blocks_container.scroll_end(animate=False)

    def action_dock_complete(self) -> None:
        """斜杠命令补全（ptk WordCompleter 同口径：仅 ^/\w*$ 时生效）"""
        text = self.text
        if not re.match(r"^/\w*$", text):
            return
        matches = [c for c in _COMMANDS if c.startswith(text)]
        if not matches:
            return
        prefix = os.path.commonprefix(matches)
        if len(prefix) > len(text):
            self.text = prefix
        elif len(matches) > 1:
            self.app.flash_hint("  ".join(matches))


class ApprovalModal(ModalScreen):
    """审批卡（v4 形态：v3 的 ptk Y/N prompt → App 内 modal）。120s 超时默认
    deny 由调用方（approve_async/approve_blocking 的 wait_for/result timeout）
    执行，模态只负责收一次决议；resolver = asyncio/concurrent Future 同形
    set_result(bool)。"""

    BINDINGS = [
        Binding("y", "approve", "执行", priority=True),
        Binding("n", "deny", "拒绝", priority=True),
        Binding("escape", "deny", "拒绝", priority=True),
    ]

    def __init__(self, tool_name: str, command: str, resolver):
        super().__init__()
        self._tool = tool_name
        self._command = str(command)[:200]
        self._resolver = resolver
        self._done = False

    def compose(self):
        with Vertical(id="approval-box"):
            yield Static(Text.assemble(("⚠ 审批 ", "bold yellow"),
                                       (f"[{self._tool}]", "bold")),
                         classes="atitle")
            yield Static(Text(f"`{self._command}`"), classes="acmd")
            yield Static("120 秒超时默认拒绝", classes="ahint")
            with Horizontal(id="abuttons"):
                yield Button("执行 (Y)", variant="success", id="approve-yes")
                yield Button("拒绝 (N)", variant="error", id="approve-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self._decide(event.button.id == "approve-yes")

    def action_approve(self) -> None:
        self._decide(True)

    def action_deny(self) -> None:
        self._decide(False)

    def _decide(self, ok: bool) -> None:
        if self._done:
            return
        self._done = True
        try:
            self._resolver.set_result(ok)
        except Exception:
            pass
        self.dismiss(ok)


class BlocksScroll(VerticalScroll):
    """对话块流（鼠标滚轮原生滚动；不抢焦点——输入 dock 保持聚焦）"""

    can_focus = False


class YuanTerminalApp(App):
    """终端 TUI v4 三区布局：状态栏 Header（常驻不重绘）+ 对话块流（
    BlocksScroll，diff 增量）+ 输入 dock（DockInput）+ 观测右栏 + 计划视图。

    renderer（TextualRenderer）= 状态唯一真相；任何状态变更经
    call_from_thread → renderer_sync 增量同步 widget（线程安全，观测轮询
    线程/查询协程/executor 三路调用统一口径）。"""

    CSS = f"""
    Screen {{
        layout: vertical;
        background: $surface;
    }}
    #header {{
        height: 1;
        dock: top;
        background: $panel;
        padding: 0 1;
    }}
    #hintbar {{
        height: 1;
        dock: bottom;
        background: $panel;
        color: $text-muted;
        padding: 0 1;
    }}
    #input {{
        height: 3;
        dock: bottom;
        border-top: solid $secondary;
        background: $surface;
        padding: 0 1;
    }}
    #body {{
        height: 1fr;
        layout: horizontal;
    }}
    #blocks {{
        width: 1fr;
        height: 100%;
    }}
    #blocks.hidden {{ display: none; }}
    #streams {{ height: auto; }}
    #stream-working, #stream-thinking, #stream-answer {{ padding: 0 1; height: auto; }}
    .hidden {{ display: none; }}
    #observe {{
        width: {OBSERVE_PANEL_W};
        height: 100%;
        display: none;
        border-left: solid $secondary;
        background: $panel;
        padding: 0 1;
    }}
    #observe.show {{ display: block; }}
    #plan {{
        width: 1fr;
        height: 100%;
        display: none;
        padding: 0 1;
    }}
    #plan.show {{ display: block; }}
    BlockWidget {{ height: auto; padding: 0 1; }}
    BlockWidget.selected {{ background: $boost; }}
    .bcontent {{ color: $text-muted; }}
    #approval-box {{
        width: 72%;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 0 2;
    }}
    #abuttons {{ height: auto; align-horizontal: center; }}
    .atitle {{ margin-top: 1; }}
    .acmd {{ margin: 0 1; }}
    .ahint {{ color: $text-muted; margin-bottom: 1; }}
    """

    BINDINGS = [
        Binding("ctrl+c", "interrupt", "停止/退出", priority=True),
        Binding("f2", "open_web", "网站对话", priority=True),
    ]

    def __init__(self, session: dict, store, renderer: "TextualRenderer"):
        super().__init__()
        self.session = session
        self.store = store
        self.renderer = renderer
        self.ctx = ReplContext(session, store, renderer, session.get("mode", "claude"))
        self.busy = False
        self._busy_task = None
        self._header_widget = None
        self._hintbar = None
        self._blocks_container = None
        self._stream_working = None
        self._stream_thinking = None
        self._stream_answer = None
        self._observe_widget = None
        self._observe_box = None
        self._plan_container = None
        self._input = None
        self._last_stream_flush = 0.0
        self._flash_until = 0.0
        self._flash_text = ""

    def compose(self):
        yield Static("", id="header")
        with Horizontal(id="body"):
            with BlocksScroll(id="blocks"):
                with Vertical(id="streams"):
                    yield Static("", id="stream-working", classes="hidden")
                    yield Static("", id="stream-thinking", classes="hidden")
                    yield Markdown("", id="stream-answer", classes="hidden")
            with BlocksScroll(id="plan"):
                yield Static("计划队列（/plan <序号> 查看步骤 · Esc/Enter 返回对话）",
                             classes="plan-title")
            with Vertical(id="observe"):
                yield Static("", id="observe-content")
        yield DockInput(id="input")
        yield Static("", id="hintbar")

    # ———— 生命周期 ————

    def on_mount(self) -> None:
        # 明暗自适应（v3 TERMINAL_DARK 同源；默认暗色）
        try:
            dark = os.getenv("TERMINAL_DARK", "1") == "1"
        except Exception:
            dark = True
        if not dark:
            self.theme = "textual-light"
        self._header_widget = self.query_one("#header", Static)
        self._hintbar = self.query_one("#hintbar", Static)
        self._blocks_container = self.query_one("#blocks", BlocksScroll)
        self._stream_working = self.query_one("#stream-working", Static)
        self._stream_thinking = self.query_one("#stream-thinking", Static)
        self._stream_answer = self.query_one("#stream-answer", Markdown)
        self._observe_widget = self.query_one("#observe-content", Static)
        self._observe_box = self.query_one("#observe", Vertical)
        self._plan_container = self.query_one("#plan", VerticalScroll)
        self._input = self.query_one(DockInput)
        self.set_focus(self._input)
        self.renderer.attach(self)
        self.renderer.set_mode(self.ctx.mode_ref[0])
        self.renderer.set_session(self.session.get("id", ""))
        self.renderer_sync()
        self.sync_hint()

    def on_resize(self, event) -> None:
        # 注意：Textual 启动时序 on_resize 先于 on_mount——守卫在 _sync_observe 内
        self._sync_observe()

    # ———— 提交/停止/快捷 ————

    async def on_submit_line(self, message: SubmitLine) -> None:
        if self.busy:
            return  # 连点守卫：handler 串行执行，第二次提交在生成中直接忽略
        line = message.line.strip()
        if not line:
            return
        self.busy = True
        self._busy_task = asyncio.current_task()
        self.sync_hint()
        ctx = self.ctx
        try:
            if ctx.render._plan_view is not None:
                ctx.render.set_plan_view(None)  # 任何输入退出计划视图（命令照常分发）
            if line.startswith("/"):
                if await dispatch_command(line, ctx) == "quit":
                    self.exit()
            else:
                await run_turn(line, ctx, rich_mode=True)
        except asyncio.CancelledError:
            # Ctrl+C 生成中：run_turn 已做停止清理；此处兜底其余 await 点
            #（/plan 网络等待等）
            ctx.render.interrupted()
            _emit_pet("idle")
        finally:
            self.busy = False
            self._busy_task = None
            self.sync_hint()

    def action_interrupt(self) -> None:
        """Ctrl+C：生成中=停止本轮（v2 语义第一下）；空闲=退出"""
        if self._busy_task is not None:
            self._busy_task.cancel()
        else:
            self.exit()

    def action_open_web(self) -> None:
        from agent.terminal import _open_web_chat
        _open_web_chat()

    # ———— renderer 状态 → widget 增量同步 ————

    def renderer_sync(self) -> None:
        """增量同步（renderer 状态变更统一入口，经 call_from_thread 线程安全）。
        diff 语义：header 文本、新增块、折叠/选中类、流式三行、计划视图切换、
        观测右栏——只动变化的 widget。"""
        render = self.renderer
        if self._header_widget is None:
            return  # on_mount 前的早到消息（call_from_thread 队列）
        self._header_widget.update(_header_text(render))
        # 块对账按 bid 身份而非下标：Textual 的 remove() 延迟生效（widget 留到
        # 下一刷新周期才出 DOM）——索引式对账会被残留块顶替（/clear 后新块
        # 挂不上、旧内容残留）。挂失补挂、多余移除，同一刷新周期内 remove+
        # mount 并存（新块最终落位正确）。
        existing = [c for c in self._blocks_container.children
                    if isinstance(c, BlockWidget)]
        by_bid = {w.bid: w for w in existing}
        wanted_bids = set()
        for i, b in enumerate(render._blocks):
            bid = b.get("bid") or uuid.uuid4().hex[:12]
            b["bid"] = bid
            wanted_bids.add(bid)
            w = by_bid.get(bid)
            if w is None:
                w = BlockWidget(bid, b.get("kind", ""), b.get("title", ""),
                                b.get("content", ""), b.get("folded", False))
                self._blocks_container.mount(w, before=self._streams)
            if w.block_folded != b.get("folded", False):
                w.set_folded(b.get("folded", False))
            w.set_class(render.sel == i, "selected")
        for w in existing:
            if w.bid not in wanted_bids:
                w.remove()  # load_history/clear 收缩
        self._sync_streams(render)
        plan_active = render._plan_view is not None
        self._blocks_container.set_class(plan_active, "hidden")
        self._plan_container.set_class(plan_active, "show")
        if plan_active:
            self._build_plan()
        self._sync_observe()
        if self._at_end():
            self._blocks_container.scroll_end(animate=False)  # 贴底跟随最新
        self.sync_hint()

    @property
    def _streams(self):
        return self.query_one("#streams", Vertical)

    def _at_end(self) -> bool:
        c = self._blocks_container
        return c.max_scroll_y - c.scroll_y < 2

    def _sync_streams(self, render) -> None:
        """流式三行：执行中工具 / 思考 / 流式回答（Markdown 节流刷新）"""
        if render._working:
            self._stream_working.update(
                Text(f"⚙ {render._working} 执行中…", style="bold yellow"))
            self._stream_working.remove_class("hidden")
        else:
            self._stream_working.add_class("hidden")
        if render._reasoning:
            self._stream_thinking.update(
                Text("思考中…\n" + render._reasoning, style="dim italic"))
            self._stream_thinking.remove_class("hidden")
        else:
            self._stream_thinking.add_class("hidden")
        if render._answer:
            now = time.time()
            if now - self._last_stream_flush >= STREAM_FLUSH_INTERVAL:
                self._last_stream_flush = now
                self._stream_answer.update((render._answer or "…") + " ▍")
            self._stream_answer.remove_class("hidden")
        else:
            self._last_stream_flush = 0.0
            self._stream_answer.add_class("hidden")

    def _build_plan(self) -> None:
        """计划队列视图（v3.2 #38 同内容：列表=状态词+进度条，详情=步骤逐行；
        rich 形态换 widget 形态——行内容与 terminal._plan_renderable 同口径）"""
        render = self.renderer
        head = render._plan_view or {}
        plan = self._plan_container
        for c in list(plan.children):
            if "plan-title" not in c.classes:
                c.remove()
        detail = head.get("detail")
        if detail:
            steps = detail.get("steps") or []
            title = str(detail.get("title") or "(无标题)")[:40]
            st = str(detail.get("status") or "draft")
            prog = int(detail.get("progress") or 0)
            plan.mount(Static(Text.assemble(
                ("▸ ", "bold"), (title, "bold"), ("  ", ""),
                (PLAN_ST_WORD.get(st, st), PLAN_ST_STYLE.get(st, "dim")),
                ("  ", ""), (f"{prog}%", ""),
                (f"  {detail.get('done_steps', 0)}/{detail.get('total_steps', 0)} 步", "dim"))))
            for s in steps:
                sst = str(s.get("status") or "pending")
                mark = {"running": "●", "done": "✔", "failed": "✗"}.get(sst, "○")
                mark_style = {"running": "yellow", "done": "green",
                              "failed": "red"}.get(sst, "dim")
                extra = f" {int(s.get('progress') or 0)}%" if sst == "running" else ""
                err = (f" {str(s.get('error') or '')[:40]}"
                       if sst == "failed" and s.get("error") else "")
                plan.mount(Static(Text.assemble(
                    (f"  {mark} 第{s.get('step_no', '?')}步 ", mark_style),
                    (f"[{str(s.get('skill') or '-')}] ", "dim"),
                    (str(s.get("desc") or "")[:30], ""),
                    (extra, "yellow"), (err, "red"))))
            return
        plans = head.get("plans")
        if not plans:
            plan.mount(Static("暂无计划——在网站对话中说「帮我制定…计划」，"
                              "创建后终端可直接看执行进度", classes="plan-empty"))
            return
        for i, p in enumerate(plans):
            title = str(p.get("title") or "(无标题)")[:34]
            st = str(p.get("status") or "draft")
            prog = max(0, min(100, int(p.get("progress") or 0)))
            plan.mount(Static(Text.assemble(
                (f"[{i + 1}] ", "bold"), (title, ""), ("  ", ""),
                (PLAN_ST_WORD.get(st, st), PLAN_ST_STYLE.get(st, "dim")),
                ("  ", ""), (f"{p.get('done_steps', 0)}/{p.get('total_steps', 0)} 步", "dim"))))
            bar = ProgressBar(total=100, show_eta=False)
            bar.progress = prog
            plan.mount(bar)

    def _sync_observe(self) -> None:
        """观测右栏（v3.2 #38 同内容；行内容与 terminal._observe_panel 共用
        _observe_lines）。宽终端（≥72）且云端通道可用才显示——与 v3 同门槛。
        守卫：Textual 启动时序 on_resize 先于 on_mount。"""
        if self._observe_widget is None:
            return
        render = self.renderer
        self._observe_widget.update(
            Text.assemble(*(Text(t, style=s) for t, s in _observe_lines(render))))
        visible = render._observe_ready and self.size.width >= 72
        self._observe_box.set_class(visible, "show")

    def sync_hint(self) -> None:
        """输入 dock 上方提示行（v3 ptk bottom_toolbar 同内容 + 忙态）"""
        render = self.renderer
        if self._hintbar is None:
            return
        if self.busy:
            self._hintbar.update(Text("生成中…（Ctrl+C 停止）", style="bold yellow"))
        elif self._flash_until > time.time():
            self._hintbar.update(Text(self._flash_text, style="cyan"))
        elif render._plan_view is not None:
            self._hintbar.update(Text("计划视图 — Esc/Enter 返回对话流 | " + _HINT_BASE))
        elif render.sel is not None:
            b = render._blocks[render.sel]
            self._hintbar.update(Text.assemble(
                ("已选中: " + b.get("title", ""), "bold"),
                (f" — Enter 展开/折叠 · Esc 取消 | {_HINT_BASE}", "")))
        else:
            self._hintbar.update(Text(_HINT_BASE, style="dim"))

    def flash_hint(self, text: str, seconds: float = 3.0) -> None:
        """临时提示（Tab 补全候选等）：到时自动回落常规提示"""
        self._flash_text = text
        self._flash_until = time.time() + seconds
        self.sync_hint()

    # ———— 审批 modal ————

    def push_approval(self, tool_name: str, command: str, resolver) -> None:
        self.push_screen(ApprovalModal(tool_name, command, resolver))

    def dismiss_approval(self) -> None:
        if isinstance(self.screen, ApprovalModal):
            self.pop_screen()


class TextualRenderer:
    """终端 TUI v4 渲染器：与 FullscreenRenderer 同接口（token/reasoning/
    tool_start/tool_end/done/error/info/interrupted + set_*/load_history/
    show_plans/tick_observation），渲染交给 Textual App（diff + 鼠标）。
    块状态与 v3 同语义——attach 前（纯状态模式）测试可直接断言。"""

    blocks_mode = True  # 支持块/计划视图/历史加载（共享命令分发鸭子判定）

    def __init__(self, cwd: str = "", session_id: str = "", status_provider=None):
        self._app = None
        self._cwd = cwd
        self._session_id = session_id
        self._status_provider = status_provider
        self._mode = "claude"
        self._backend = ""
        self._blocks: list = []
        self._answer = ""
        self._reasoning = ""
        self._think_start = None
        self._tool_count = 0
        self._working = None
        self.sel = None
        self._observe = None
        self._observe_ready = False
        self._usage = None
        self._plan_view = None

    # ———— App 生命周期 ————

    def attach(self, app) -> None:
        self._app = app

    def detach(self) -> None:
        self._app = None

    def _post(self, fn, *args) -> None:
        """App 线程直调 / 跨线程投递（Textual 8 的 call_from_thread 拒绝同
        线程调用）。detach 后静默 no-op。"""
        app = self._app
        if app is None:
            return
        try:
            if threading.get_ident() == app._thread_id:
                fn(*args)
            else:
                app.call_from_thread(fn, *args)
        except Exception:
            pass

    def _notify(self) -> None:
        """状态已变 → 通知 App 增量同步。调用来源分两路：
        - App 事件循环线程（查询协程/输入提交 handler）= 直接同步调用
        - 其他线程（观测轮询 daemon / claude_loop executor）= call_from_thread
          投递消息，队列 FIFO 保序、线程安全
        detach/未 attach（纯状态模式）静默 no-op。"""
        app = self._app
        if app is not None:
            self._post(app.renderer_sync)

    # ———— 状态设置（共享命令分发调用） ————

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._notify()

    def set_session(self, session_id: str) -> None:
        self._session_id = session_id
        self._notify()

    def set_backend(self, backend: str) -> None:
        """执行后端（v3.1 #37）：backend_event 驱动——local=本机统筹执行 /
        cloud=云端执行；状态栏可见（云边协同透明化）"""
        self._backend = ("local" if backend == "local"
                         else "cloud" if backend == "cloud" else "")
        self._notify()

    def load_history(self, messages: list) -> None:
        """云端会话历史 → 块（v3.1 /sessions 切换与 /chat 进入时用）：
        user → 「你 ▸」块、assistant → answer 块；其余跳过。"""
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
        self.sel = None
        self._notify()

    def clear_blocks(self) -> None:
        """清空全部对话块（/clear 命令；与 FullscreenRenderer 同接口）"""
        self._blocks.clear()
        self.sel = None
        self._notify()

    def redraw(self) -> None:
        """全量同步（Textual 增量渲染——等价重绘，实际只动变化 widget）"""
        self._notify()

    def set_usage(self, total: int, cached: int = 0) -> None:
        """上轮 token 消耗（usage_event，run_cloud_query 消费）"""
        self._usage = {"total": int(total or 0), "cached": int(cached or 0)}
        self._notify()

    def tick_observation(self, data: dict) -> None:
        """观测轮询线程注入（15s /chat/cc-activity）：只更新状态；渲染时机
        由 call_from_thread 投递——Textual 刷新线程安全，无需 v3 的
        _prompt_active 守卫（无 ptk 输入行打架问题）"""
        self._observe = data or None
        self._notify()

    # ———— 计划视图（v3.2 #38 同语义） ————

    def set_plan_view(self, data) -> None:
        """None = 退出计划视图（回到对话流块）"""
        self._plan_view = data
        self._notify()

    def show_plans(self, plans: list, detail: dict = None) -> None:
        """计划列表或单计划详情进全屏视图"""
        self._plan_view = {"plans": plans or [], "detail": detail}
        self.sel = None
        self._notify()

    # ———— 折叠/选中交互（DockInput 键盘操作） ————

    def toggle_fold(self, idx: int) -> None:
        blocks = self._blocks
        if 0 <= idx < len(blocks) and blocks[idx].get("kind") in ("thinking", "tool"):
            blocks[idx]["folded"] = not blocks[idx].get("folded", False)
            self._notify()

    # ———— 流式接口（与 Plain/Rich/Fullscreen 对齐） ————

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
        self._notify()

    def reasoning(self, text: str) -> None:
        if self._think_start is None:
            self._think_start = time.time()
        self._reasoning += text
        self._notify()

    def tool_start(self, name: str) -> None:
        self._tool_count += 1  # 先计数：思考块标题「N 次工具调用」含本次
        self._snapshot_thinking()
        self._working = name
        self._notify()

    def tool_end(self, name: str, output: str) -> None:
        out = (output if len(output) <= MAX_TOOL_OUTPUT
               else output[:MAX_TOOL_OUTPUT] + "\n...(输出过长已截断)")
        self._blocks.append({"kind": "tool", "title": f"⚙ {name}",
                             "content": out, "folded": True})
        self._working = None
        self._notify()

    def done(self) -> None:
        self._snapshot_thinking(final=True)
        if self._answer:
            self._blocks.append({"kind": "answer", "title": "",
                                 "content": self._answer, "folded": False})
            self._answer = ""
        self._notify()

    def error(self, text: str) -> None:
        self._blocks.append({"kind": "error", "title": "", "content": text,
                             "folded": False})
        self._notify()

    def info(self, text: str) -> None:
        self._blocks.append({"kind": "info", "title": "", "content": text,
                             "folded": False})
        self._notify()

    def interrupted(self) -> None:
        self._answer = ""
        self._blocks.append({"kind": "info", "title": "", "content": "（已停止生成）",
                             "folded": False})
        self._notify()

    # ———— 审批（v4 modal 形态；v3 语义不变：120s 超时默认 deny） ————

    async def approve_async(self, tool_name: str, command: str) -> str:
        """云端通道审批（run_cloud_query 在 App 事件循环内 await）：推 modal
        → 等决议；超时默认 deny 并收起 modal。"""
        if self._app is None:
            return "deny"
        fut = asyncio.get_running_loop().create_future()
        self._post(self._app.push_approval, tool_name, command, fut)
        try:
            ok = await asyncio.wait_for(fut, timeout=120)
            return "approve" if ok else "deny"
        except Exception:
            self._post(self._app.dismiss_approval)
            return "deny"

    def approve_blocking(self, decision_id: str, tool_name: str, command: str) -> str:
        """本机 /claude 审批（claude_loop 经 executor 线程同步阻塞调用）：
        推 modal → 阻塞等决议；超时默认 deny 并收起 modal。"""
        if self._app is None:
            return "deny"
        fut = concurrent.futures.Future()
        self._post(self._app.push_approval, tool_name, command, fut)
        try:
            ok = fut.result(timeout=120)
            return "approve" if ok else "deny"
        except Exception:
            self._post(self._app.dismiss_approval)
            return "deny"


async def run_textual_repl(session: dict, store, render: TextualRenderer) -> None:
    """v4 Textual 交互循环（terminal.run_repl 委托；运行失败上抛由调用方
    回退 v3 ptk 路径——降级链保留）。观测轮询与 v3 同源（15s /chat/cc-activity，
    /claude 模式也可用）；仅生产路径启动——测试直驱 YuanTerminalApp 不经此函数
    不会起线程。App 自带 alt-screen（driver 写 ?1049h），scrollback 天然干净。"""
    from agent.terminal import _make_cloud_client, _start_observe_poll
    app = YuanTerminalApp(session, store, render)
    client = _make_cloud_client()
    if client is not None:
        render._observe_ready = True
        _start_observe_poll(render, lambda: client)
    await app.run_async()
    render.detach()
