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

审查修复批次（2026-11-15 五角度审查后）：
- **回合不阻塞消息泵**：submit_line 同步创建独立任务跑回合——此前 handler 内
  整段 await 致泵阻塞（Ctrl+C 停不下且回合结束后误退出 + 审批 modal 死锁
  120s 自动拒绝 + 生成中滚轮/输入全部排队）
- **流式快速路径**：token/reasoning 走 stream scope（只刷流式三行+跟随滚动），
  header/hint/observe/plan 全部签名比对防每 token 重建（性能审查：此前每
  token 全量对账重演「抽搐」）
- Esc 武装限时/被其它键解除；Tab 补全后光标归位；选中态 Enter 不提交；
  审批 modal 默认焦点=拒绝（v3 [y/N] fail-closed）；停止时收起审批卡；
  interrupted/error 清流式残留；历史文件与 ptk FileHistory 同格式（同一数据
  实体单一写路径）；观测接线/命令清单/截断/历史映射共享 terminal 助手
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
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widgets import Button, Input, Markdown, OptionList, ProgressBar, Static, TextArea
from textual.widgets._option_list import Option

from agent.terminal import (  # terminal 懒加载本模块，反向引用安全
    HISTORY_FILE,
    OBSERVE_PANEL_W,
    PLAN_ST_STYLE,
    PLAN_ST_WORD,
    SLASH_COMMANDS,
    ReplContext,
    _emit_pet,
    _header_text,
    _observe_lines,
    _truncate_tool_output,
    _wire_observe,
    dispatch_command,
    history_to_blocks,
    run_turn,
)

# 流式刷新节流（秒）：窗口内 token 累积、到点一次刷新（Markdown.append 增量
# 解析 + 50ms ≈ 20fps——用户「不丝滑」反馈后收紧）
STREAM_FLUSH_INTERVAL = 0.05

# Esc+Enter 换行和弦窗口（秒）：Esc 后此窗口内按 Enter = 换行；超时自动解除
# ——单按 Esc 不劫持后续 Enter（用户实测「回车发送交互不好」根因之一）
ESC_ARM_WINDOW = 1.2

_HINT_BASE = "↑↓ 选择 · Enter 展开/折叠 · PgUp/PgDn 滚动 · Esc+Enter 换行 · Ctrl+C 停止 · ? 帮助"

# 说话人身份标签（网页端 MessageBubble 同款：色点 + 名称 + AI 徽标；
# 用户反馈「混在模型输出里分辨不了」——气泡身份对齐网页 agents.ts 配色）
AGENT_LABELS = {"orchestrator": ("小元AI", "blue"),
                "claude": ("Claude Code", "orange3"),
                "automation": ("自动化", "orange1"),
                "cloud_fallback": ("云端兜底", "grey58")}


def _agent_label_text(sender: str) -> Text:
    """身份标签行：● 色点 + 名称 + AI 徽标（C5 标识办法同网页气泡）"""
    label, color = AGENT_LABELS.get(sender or "orchestrator", AGENT_LABELS["orchestrator"])
    return Text.assemble((f"● {label}", f"bold {color}"), ("  AI", "dim"))


class BlockWidget(Vertical):
    """对话块容器（网页端 MessageBubble 同款形态，用户反馈「混在模型输出里
    分辨不了」后对齐）：
    - user = 右对齐品牌蓝底白字气泡（网页 var(--accent) 底 + #fff 字 + 右圆角）
    - answer = 左对齐气泡：身份标签行（● 色点 + 名称 + AI 徽标）+ 左侧品牌
      色条 + 面板底（网页 bg-tertiary + 3px 身份色条）
    - info/error = 居中弱化行；thinking/tool = 折叠块（标题行 + 展开内容）
    folded 切换 = 内容子件挂载/卸载（in-place，不重建 widget）。选中态
    .selected 由 app 同步。"""

    def __init__(self, bid: str, kind: str, title: str, content: str, folded: bool,
                 sender: str = "orchestrator"):
        super().__init__(classes=f"block {kind}-block")
        self.bid = bid
        self.block_kind = kind
        self.block_title = title
        self.block_content = content
        self.block_folded = bool(folded)
        self.block_sender = sender or "orchestrator"

    def compose(self):
        kind = self.block_kind
        if kind == "answer":
            yield Static(_agent_label_text(self.block_sender), classes="alabel")
            yield Markdown(self.block_content or "（空）", classes="abubble")
        elif kind == "user":
            # 右对齐需容器级 align（Textual 8 子件级 align-horizontal 不生效）
            with Horizontal(classes="urow"):
                yield Static(Text(self.block_content, style="bold"), classes="ububble")
        elif kind == "info":
            yield Static(Text(self.block_content, style="dim"), classes="iline")
        elif kind == "error":
            yield Static(Text(f"✗ {self.block_content}", style="bold red"), classes="iline")
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


class HistoryModal(ModalScreen):
    """Ctrl+R 命令历史（v4 形态；2026-11-15 升级 CC 同款增量搜索）：
    顶部过滤输入 + 结果列表——键入即过滤，↓ 进列表 ↑↓ 选择，Enter/点击回填。"""

    BINDINGS = [
        Binding("escape", "cancel", "取消", priority=True),
        Binding("down", "focus_list", "选结果", priority=True),
    ]

    def __init__(self, items: list):
        super().__init__()
        self._all = list(items)[-100:][::-1]  # 最近在前

    def compose(self):
        with Vertical(id="history-box"):
            yield Static("命令历史（输入过滤 · ↓ 进列表选择 · Enter 回填 · Esc 取消）",
                         classes="hstitle")
            yield Input(placeholder="搜索历史命令…", id="hfilter")
            yield OptionList(*self._build_options(self._all), id="hlist")

    @staticmethod
    def _build_options(items):
        return [Option(item, id=f"h{i}") for i, item in enumerate(items)]

    def on_input_changed(self, event) -> None:
        """增量过滤：键入即筛（CC Ctrl+R 同款）"""
        q = event.value.strip().lower()
        opts = [o for o in self._all if q in o.lower()]
        lst = self.query_one("#hlist", OptionList)
        lst.clear_options()
        lst.add_options(self._build_options(opts))

    def action_focus_list(self) -> None:
        self.set_focus(self.query_one("#hlist", OptionList))

    def on_option_list_option_selected(self, event) -> None:
        self.dismiss(event.option.prompt)

    def action_cancel(self) -> None:
        self.dismiss(None)


_HELP_TEXT = """[bold blue]命令[/bold blue]
  /claude   CC 窗口（与网站 CC 窗口同一会话，本机执行）
  /chat     小元窗口（网站主对话，多端同步）
  /local    本机直连（Claude SDK 草稿，不与网站同步）
  /sessions 当前窗口会话列表 / 切换（/sessions <序号>）
  /new      新建会话（按当前窗口，对称网页「新对话」）
  /plan     计划队列（/plan <序号> 看步骤）
  /web      打开网站对话    /status 本机状态
  /panel    打开设置面板    /pet on|off 桌宠
  /history  本机直连会话    /clear 清空显示
  /quit     退出

[bold blue]按键[/bold blue]
  Enter 发送 · Esc+Enter 换行 · ↑↓ 选块 · Enter 展开/折叠
  PgUp/PgDn 滚动 · End 回到底部 · Tab 补全命令
  Ctrl+R 搜索历史 · F2 网站对话 · Ctrl+C/Ctrl+Q 停止/退出

[bold blue]说明[/bold blue]
  本地终端第三端：/chat 与 /claude 的消息网站立即可见，
  网站发的消息终端同样同步。
  审批弹窗 Y 执行 / N 拒绝（回车=拒绝，120 秒超时默认拒绝）。
  执行过程见对话中的工具行；本机活动见右栏与 /status。"""


class HelpModal(ModalScreen):
    """? 帮助浮层（#39 品牌批 v4 化，CC 帮助面板同款形态）：命令/按键/说明
    一屏速查。? 键与 /help 同入口。"""

    BINDINGS = [
        Binding("escape", "cancel", "关闭", priority=True),
        Binding("q", "cancel", "关闭", priority=True),
    ]

    def compose(self):
        with Vertical(id="help-box"):
            yield Static(Text.assemble(("小元AI", "bold blue"),
                                       (" · 云边协同 · 对话即执行", "dim")),
                         classes="htitle")
            yield Static(Text.from_markup(_HELP_TEXT), classes="hbody", id="hbody")

    def action_cancel(self) -> None:
        self.dismiss(None)


class DockInput(TextArea):
    """输入 dock：Enter 提交（计划视图退出/选中块优先；生成中忽略）、
    Esc+Enter 换行、↑↓ 块选择、PgUp/PgDn 滚动、End 回到底部、Tab 斜杠命令
    补全、Ctrl+R 历史。v3 ptk 交互语义不动（#36 键盘契约）。"""

    BINDINGS = [
        Binding("enter", "dock_enter", "提交", priority=True),
        Binding("escape", "dock_escape", "取消", priority=True),
        Binding("up", "dock_up", "上一块", priority=True),
        Binding("down", "dock_down", "下一块", priority=True),
        Binding("pageup", "dock_page_up", "上翻", priority=True),
        Binding("pagedown", "dock_page_down", "下翻", priority=True),
        Binding("end", "dock_end", "回到底部", priority=True),
        Binding("tab", "dock_complete", "补全", priority=True),
        Binding("ctrl+r", "dock_history", "历史", priority=True),
        Binding("question_mark", "dock_help", "帮助", priority=True),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(show_line_numbers=False, *args, **kwargs)
        self._esc_armed = False  # Esc 后限时内 Enter = 换行（ptk escape+enter 和弦同款）
        self._esc_timer = None   # 武装窗口定时器（用户实测：粘性武装曾让
        # 之后任何一次 Enter 都插换行不发送——单按 Esc 不该劫持后续 Enter）

    def on_mount(self) -> None:
        # 输入历史：与 v3 prompt_toolkit FileHistory 同文件同格式（'+' 行 +
        # 时间戳注释）——同一数据实体单一写路径（CLAUDE.md 教训 #3），
        # 纯文本重写会把 v4 输入从 v3 ↑ 历史里抹掉
        try:
            from prompt_toolkit.history import FileHistory
            # load_history_strings 返回最近在前的反向迭代器——倒序还原时序
            self._history = list(FileHistory(HISTORY_FILE).load_history_strings())[::-1]
        except Exception:
            self._history = []

    def on_key(self, event) -> None:
        if event.key != "escape":
            self._esc_armed = False  # 任意其它键解除 Esc 武装（审查修复：
            # 此前武装永不解除，Esc 后首次 Enter 误插换行不提交）

    def _disarm_esc(self) -> None:
        self._esc_armed = False
        if self._esc_timer is not None:
            self._esc_timer.stop()
            self._esc_timer = None

    def _remember(self, line: str) -> None:
        if not line.strip():
            return  # 空行不进历史（补漏扫描：回车空输入曾写入空条目污染 ↑ 历史）
        self._history.append(line)
        if len(self._history) > 500:
            self._history = self._history[-500:]
        try:
            from prompt_toolkit.history import FileHistory
            FileHistory(HISTORY_FILE).store_string(line)  # ptk 格式追加
        except Exception:
            pass

    def _scroll_target(self):
        """滚动目标：计划视图滚计划容器，否则滚对话块流（审查修复：此前
        PgUp/PgDn 恒滚块流，计划视图键盘翻页失效）"""
        app = self.app
        if app.renderer._plan_view is not None:
            return app._plan_container
        return app._blocks_container

    def action_dock_enter(self) -> None:
        app = self.app
        render = app.renderer
        if app.busy:
            # 生成中忽略提交但给反馈（用户实测「回车交互不好」——此前静默无感）
            app.flash_hint("生成中——等待完成或 Ctrl+C 停止后再发送")
            return
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
            return  # v3 同款：任何选中态 Enter 只刷新不提交（审查修复：
            # 此前非折叠块选中时 Enter 会把半写消息发给模型）
        line = self.text
        self._remember(line)
        app.submit_line(line)
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
            # 和弦窗口（用户实测：粘性武装曾劫持之后每次 Enter 误插换行）
            if self._esc_timer is not None:
                self._esc_timer.stop()
            self._esc_timer = self.set_timer(ESC_ARM_WINDOW, self._disarm_esc)
        app.sync_hint()

    def action_dock_up(self) -> None:
        self._disarm_esc()
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
        self._disarm_esc()
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
        self._disarm_esc()
        target = self._scroll_target()
        target.scroll_page_up()
        if target is self.app._blocks_container:
            self.app._following = False  # 键盘回看 = 暂停跟随（同滚轮语义）

    def action_dock_page_down(self) -> None:
        self._disarm_esc()
        target = self._scroll_target()
        target.scroll_page_down()
        if target is self.app._blocks_container:
            target.call_after_refresh(target._maybe_refollow)

    def action_dock_end(self) -> None:
        self._disarm_esc()
        target = self._scroll_target()
        target.scroll_end(animate=False)
        if target is self.app._blocks_container:
            self.app._following = True  # End 回底 = 恢复跟随

    def action_dock_complete(self) -> None:
        """斜杠命令补全（ptk WordCompleter 同口径：仅 ^/\w*$ 时生效；
        清单与 v3 共用 SLASH_COMMANDS 单一事实源）"""
        self._disarm_esc()
        text = self.text
        if not re.match(r"^/\w*$", text):
            return
        matches = [c for c in SLASH_COMMANDS if c.startswith(text)]
        if not matches:
            return
        prefix = os.path.commonprefix(matches)
        if len(prefix) > len(text):
            self.text = prefix
            # 审查修复：load_text 把光标重置到 (0,0)——补到末尾，否则后续
            # 输入插在命令前面（'/pl'+Tab+' 3' 曾变 ' 3/plan'）
            self.move_cursor((0, len(prefix)))
        elif len(matches) > 1:
            self.app.flash_hint("  ".join(matches))

    def action_dock_history(self) -> None:
        self._disarm_esc()
        self.app.open_history_modal()

    def action_dock_help(self) -> None:
        self._disarm_esc()
        self.app.open_help_modal()


class _NoFocusButton(Button):
    """不可聚焦按钮：Tab/回车永不落在「执行」上——v3 [y/N] fail-closed 语义
    （审查修复：modal 自动聚焦第一个可聚焦件，「执行」曾获默认焦点致回车即
    批准；Y 键是键盘批准路径，与标签 (Y) 一致）"""

    can_focus = False


class ApprovalModal(ModalScreen):
    """审批卡（用户实测「审批搞那么大」→ 2026-11-15 紧凑化，网页 ApprovalCard
    同款：maxWidth 卡片 + 小按钮）。120s 超时默认 deny 由调用方执行，模态只
    收一次决议；resolver = asyncio/concurrent Future 同形 set_result(bool)。
    回车=拒绝（v3 [y/N] fail-closed，显式绑定不依赖焦点落点）。"""

    BINDINGS = [
        Binding("y", "approve", "执行", priority=True),
        Binding("n", "deny", "拒绝", priority=True),
        # v3 [y/N] fail-closed：回车=拒绝——显式绑定，不依赖焦点落点
        #（焦点时序有竞态：auto-focus 与 call_after_refresh 谁先到不确定，
        # 测试偶发抓出）
        Binding("enter", "deny", "拒绝", priority=True),
        Binding("escape", "deny", "拒绝", priority=True),
    ]

    def __init__(self, tool_name: str, command: str, resolver):
        super().__init__()
        self._tool = tool_name
        self._command = str(command)[:80]
        self._resolver = resolver
        self._done = False

    def compose(self):
        with Vertical(id="approval-box"):
            yield Static(Text.assemble(("⚠ 审批 ", "bold yellow"),
                                       (f"[{self._tool}]", "bold"),
                                       ("  ", ""),
                                       (f"`{self._command}`", "dim")),
                         classes="acmd")
            with Horizontal(id="abuttons"):
                yield _NoFocusButton("执行 (Y)", variant="success", id="approve-yes")
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
        try:
            if self.app.screen is self:
                self.dismiss(ok)  # 已被外部弹屏（Ctrl+C 收起）时不再二次弹
        except Exception:
            pass

    def on_unmount(self) -> None:
        # 任何未经决议的关闭（Ctrl+C 收起/退出）都解析为拒绝——补漏扫描：
        # dismiss_approval 只弹屏不决议，approve_blocking 的 executor 线程
        # 会阻塞到 120s 超时，asyncio.run 关停等待该线程致进程假死
        self._decide(False)


class BlocksScroll(VerticalScroll):
    """对话块流/计划视图滚动容器（鼠标滚轮原生；不抢焦点——输入 dock 保持聚焦）。

    follow_tracking=True（仅 #blocks 实例）时维护贴底跟随态——**事件驱动**
    （用户实测：「滚轮不能滑动/结束停首页」根因=watch_scroll_y 把 reflow 引起
    的 scroll_y 抖动误判为用户滚动：跟随被误杀、流式 flush 又把滚轮拉回底部）。
    用户信号三路：鼠标滚轮上滑（事件）、PgUp/End（键盘 action）、滚动条拖拽
    （grabbed 时 watch）；其余 scroll_y 变化一律视为程序/reflow，不干预。"""

    can_focus = False
    follow_tracking = False

    def on_mouse_scroll_up(self, event) -> None:
        """滚轮上滑 = 用户主动回看历史 → 暂停贴底跟随（生成中的 flush 不再
        拉回底部）"""
        if self.follow_tracking:
            self.app._following = False

    def on_mouse_scroll_down(self, event) -> None:
        """滚轮下滑：滚回底部附近恢复跟随（滚动落位后判定）"""
        if self.follow_tracking:
            self.call_after_refresh(self._maybe_refollow)

    def _maybe_refollow(self) -> None:
        if self.is_vertical_scroll_end:
            self.app._following = True

    def watch_scroll_y(self, old: int, new: int) -> None:
        """仅滚动条拖拽时解读为用户操作（拖拽不经滚轮事件）；reflow/程序
        滚动不带 grabbed 标记，不误判"""
        if not self.follow_tracking or not self.is_vertical_scrollbar_grabbed:
            return
        if new < old:
            self.app._following = False
        elif new >= self.max_scroll_y - 2:
            self.app._following = True


# T2 品牌对齐（2026-11-18）：色板与网站 index.css 变量对偶。Textual 8 的
# CSS tokenizer 不支持在规则内声明 `$var:`——主题色走 Theme 注册
# （App.register_theme；$text/$text-muted 等派生变量由 ColorSystem 从
# foreground 生成）。对应关系：surface=--bg-primary / panel=--bg-secondary /
# boost=--bg-tertiary / primary=--accent / secondary=--border /
# foreground=--text-primary；primary-solid=用户气泡底（variables 扩展键，
# 暗色下用深调——浅蓝底白字对比不足）。
_YUANAI_THEMES = {
    "yuanai-light": Theme(
        name="yuanai-light",
        primary="#2563eb",
        secondary="#cbd5e1",
        warning="#d97706",
        error="#dc2626",
        success="#16a34a",
        foreground="#0f172a",
        background="#f8fafc",
        surface="#f8fafc",
        panel="#f1f5f9",
        boost="#e2e8f0",
        dark=False,
    ),
    "yuanai-dark": Theme(
        name="yuanai-dark",
        primary="#60a5fa",
        secondary="#2b3b56",
        warning="#fbbf24",
        error="#f87171",
        success="#4ade80",
        foreground="#e2e8f0",
        background="#0b1220",
        surface="#0b1220",
        panel="#101a2c",
        boost="#16233a",
        dark=True,
    ),
}


class YuanTerminalApp(App):
    """终端 TUI v4 三区布局：状态栏 Header（常驻不重绘）+ 对话块流（
    BlocksScroll，diff 增量）+ 输入 dock（DockInput）+ 观测右栏 + 计划视图。

    renderer（TextualRenderer）= 状态唯一真相；状态变更经 _post（App 线程直调
    / 跨线程 call_from_thread）→ renderer_sync 增量同步。**回合在独立任务里
    跑**（submit_line 创建）——消息泵不被整段阻塞，Ctrl+C/审批/滚轮全程可用。"""

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
    /* 网页端气泡形态（用户反馈「混在模型输出里分辨不了」后对齐
       MessageBubble）：用户=右对齐品牌蓝底白字；AI=左对齐面板底 + 左侧
       品牌色条 + 身份标签行（$primary 两种主题均为蓝，白字对比最佳）。
       气泡样式挂子件——容器 width:auto 会致内容测量塌缩（标签一字一行、
       内容不可见，真机截图抓出） */
    BlockWidget.user-block .urow {{ align-horizontal: right; }}
    BlockWidget.user-block .ububble {{
        width: auto; max-width: 80%;
        background: $primary; color: #ffffff; padding: 0 1; text-style: bold;
    }}
    BlockWidget.answer-block .abubble {{
        background: $panel; border-left: heavy $primary; padding: 0 1;
    }}
    /* 思考/工具行并入回答气泡视觉（同面板底 + 同左边条——与回答连续成
       一体，网页端「气泡内折叠区/工具卡」同款；用户实测「这终端好乱」） */
    BlockWidget.thinking-block, BlockWidget.tool-block {{
        background: $panel; border-left: heavy $primary; padding: 0 1;
    }}
    .bcontent {{ color: $text-muted; }}
    #stream-answer-label {{ height: 1; }}
    #stream-answer {{
        border-left: heavy $primary; background: $panel;
    }}
    #approval-box {{
        width: 64%;
        max-width: 80;
        height: auto;
        border: round $warning;
        background: $surface;
        padding: 0 1;
    }}
    #abuttons {{ height: auto; align-horizontal: left; margin-left: 1; }}
    .acmd {{ margin-top: 1; }}
    #abuttons Button {{ min-width: 12; padding: 0 1; }}
    .ahint {{ color: $text-muted; margin-bottom: 1; }}
    #history-box {{
        width: 70%;
        height: 70%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }}
    .hstitle {{ margin-bottom: 1; }}
    #hfilter {{ margin-bottom: 1; }}
    #hlist {{ height: 1fr; }}
    /* P1（2026-11-15，D4 拍板仅 CC 窗口）：执行时间线形态——扁平块全宽 +
       左色条（网站 exec 视觉语言，CC 身份棕 #e8a06b）；身份标签行隐藏
       （状态栏「CC 窗口」徽标替代） */
    YuanTerminalApp.exec-mode BlockWidget.user-block .urow {{
        align-horizontal: left;
    }}
    YuanTerminalApp.exec-mode BlockWidget.user-block .ububble {{
        width: 1fr; max-width: 100%; background: $panel;
        color: $text; text-style: none; border-left: heavy #e8a06b;
    }}
    YuanTerminalApp.exec-mode BlockWidget.answer-block .abubble {{
        border-left: heavy #e8a06b;
    }}
    /* T2（2026-11-18）：暗色下用户气泡底换深调 #1d4ed8——$primary 在
       yuanai-dark 里是浅蓝 #60a5fa，白字对比不足（-dark-mode 类随主题
       dark 标记自动挂载；特异性高于基础气泡规则） */
    YuanTerminalApp.-dark-mode BlockWidget.user-block .ububble {{
        background: #1d4ed8;
    }}
    YuanTerminalApp.exec-mode BlockWidget.thinking-block,
    YuanTerminalApp.exec-mode BlockWidget.tool-block {{
        border-left: heavy #e8a06b;
    }}
    YuanTerminalApp.exec-mode BlockWidget.answer-block .alabel {{
        display: none;
    }}
    #help-box {{
        width: 80%;
        height: 85%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }}
    .htitle {{ text-style: bold; margin-bottom: 1; }}
    #hbody {{ height: 1fr; }}
    """

    BINDINGS = [
        Binding("ctrl+c", "interrupt", "停止/退出", priority=True),
        # Ctrl+Q 覆盖 Textual 默认 quit 绑定（补漏扫描：默认绑定绕过停止语义——
        # 生成中直接退出，在途回合不落库/审批线程被搁置）。与 Ctrl+C 同语义
        Binding("ctrl+q", "interrupt", "停止/退出", priority=True),
        Binding("f2", "open_web", "网站对话", priority=True),
    ]

    def __init__(self, session: dict, store, renderer: "TextualRenderer"):
        super().__init__()
        # T2 品牌主题注册（2026-11-18）：网站色板对偶；apply_theme 按名切换
        self.register_theme(_YUANAI_THEMES["yuanai-light"])
        self.register_theme(_YUANAI_THEMES["yuanai-dark"])
        self.session = session
        self.store = store
        self.renderer = renderer
        self.ctx = ReplContext(session, store, renderer, [session.get("mode", "claude")])
        self.resume = None  # run_textual_repl 注入：{"mode","sid","messages"}
        # 云端窗口启动接续（本地终端第三端）；None = 回退本机历史
        self._busy_task = None  # 回合任务（独立于消息泵；busy 属性由它派生）
        self._header_widget = None
        self._hintbar = None
        self._blocks_container = None
        self._stream_working = None
        self._stream_thinking = None
        self._stream_answer = None
        self._stream_answer_label = None
        self._flushed_len = 0        # 已 flush 进 Markdown.append 的字符数（增量）
        self._stream_sender = "orchestrator"
        self._observe_widget = None
        self._observe_box = None
        self._plan_container = None
        self._input = None
        # 签名/版本缓存（性能审查：避免每 token 重建不变的内容）
        self._header_sig = None
        self._hint_sig = None
        self._observe_sig = None
        self._plan_sig = None
        self._block_count = -1
        self._content_version = 0
        self._last_scroll_version = -1
        self._last_stream_flush = 0.0
        self._last_think_flush = None
        self._flash_until = 0.0
        self._flash_text = ""
        self._flash_timer = None
        self._following = True  # 贴底跟随态（BlocksScroll.watch_scroll_y 维护）
        self._exec_sig = None  # exec-mode（CC 窗口执行时间线形态）签名

    @property
    def busy(self) -> bool:
        return self._busy_task is not None

    def apply_theme(self, theme: str) -> None:
        """主题应用唯一入口（T2：/theme 命令与启动链共用；v3 遗留的
        TERMINAL_DARK 直设已收敛到 terminal_theme.resolve_startup_theme）"""
        self.theme = "yuanai-dark" if theme == "dark" else "yuanai-light"

    def compose(self):
        yield Static("", id="header")
        with Horizontal(id="body"):
            with BlocksScroll(id="blocks") as blocks_scroll:
                blocks_scroll.follow_tracking = True
                with Vertical(id="streams"):
                    yield Static("", id="stream-working", classes="hidden")
                    yield Static("", id="stream-thinking", classes="hidden")
                    yield Static("", id="stream-answer-label", classes="hidden")
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
        # T2 品牌对齐（2026-11-18）：主题跟随 = 云端 my-theme（设备凭据）→
        # data/theme.json 缓存 → TERMINAL_DARK 环境（v3 兼容）→ 默认暗色
        from agent.terminal_theme import resolve_startup_theme
        self.apply_theme(resolve_startup_theme())
        self._header_widget = self.query_one("#header", Static)
        self._hintbar = self.query_one("#hintbar", Static)
        self._blocks_container = self.query_one("#blocks", BlocksScroll)
        self._stream_working = self.query_one("#stream-working", Static)
        self._stream_thinking = self.query_one("#stream-thinking", Static)
        self._stream_answer = self.query_one("#stream-answer", Markdown)
        self._stream_answer_label = self.query_one("#stream-answer-label", Static)
        self._observe_widget = self.query_one("#observe-content", Static)
        self._observe_box = self.query_one("#observe", Vertical)
        self._plan_container = self.query_one("#plan", BlocksScroll)
        self._input = self.query_one(DockInput)
        self.set_focus(self._input)
        self.renderer.attach(self)
        self.renderer.set_mode(self.ctx.mode_ref[0])
        if self.resume is not None:
            # 启动即接续云端窗口（本地终端第三端，用户拍板 2026-11-15）：
            # claude=网站 CC 窗口 / chat=小元主对话——与网站完全同步
            self.ctx.mode_ref[0] = self.resume["mode"]
            self.ctx.cloud_sid = self.resume["sid"]
            self.ctx.cloud_messages = list(self.resume["messages"])
            self.renderer.set_mode(self.resume["mode"])
            self.renderer.set_session(self.resume["sid"])
            self.renderer.load_history(
                self.resume["messages"],
                "claude" if self.resume["mode"] == "claude" else "orchestrator")
        else:
            # 云端不可达/无身份：回退本机历史显示（/local 草稿会话）
            self.renderer.set_session(self.session.get("id", ""))
            self.renderer.load_history(
                self.session.get("messages") or [],
                "claude" if self.session.get("mode") == "claude" else "orchestrator")
        self.renderer_sync()
        self.sync_hint()

    def on_resize(self, event) -> None:
        # call_after_refresh：on_resize 先于 App 内部尺寸更新（审查修复：
        # 此前读到旧 size，缩窗后观测右栏滞留到下一次 sync）
        self.call_after_refresh(self._sync_observe)

    # ———— 提交/停止/快捷 ————

    def submit_line(self, line: str) -> None:
        """输入 dock 提交（同步、立即返回）。回合在独立 asyncio 任务里跑——
        审查根因修复：此前 on_submit_line handler 内整段 await 回合，Textual
        消息泵被阻塞到生成结束——Ctrl+C 停不下（队列里的 Ctrl+C 在回合结束后
        走空闲分支直接退出 app）、审批 modal 死锁 120s 自动拒绝、生成中
        滚轮/输入全部排队。"""
        line = line.strip()
        if not line:
            return
        if self.busy:
            return  # 连点守卫
        self._busy_task = asyncio.create_task(self._handle_line(line))
        self.sync_hint()

    async def _handle_line(self, line: str) -> None:
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
            # （/plan 网络等待等）
            ctx.render.interrupted()
            _emit_pet("idle")
        except Exception as e:
            ctx.render.error(f"处理失败：{str(e)[:160]}")
        finally:
            self._busy_task = None
            self.sync_hint()

    def action_interrupt(self) -> None:
        """Ctrl+C/Ctrl+Q：生成中=停止本轮（v2 语义第一下）；空闲=退出"""
        if self._input is not None:
            self._input._disarm_esc()  # App 级按键不经 DockInput.on_key——
            # 补漏扫描：Esc 武装曾在 Ctrl+C 后残留，下次 Enter 误插换行
        if self._busy_task is not None:
            self.dismiss_approval()  # 停止时收起审批卡（CancelledError 不过
                                     # except Exception，modal 会滞留）
            self._busy_task.cancel()
        else:
            self.exit()

    def action_open_web(self) -> None:
        if self._input is not None:
            self._input._disarm_esc()
        from agent.terminal import _open_web_chat
        _open_web_chat()

    def open_history_modal(self) -> None:
        """Ctrl+R 历史（CC 同款增量搜索：键入过滤 + ↓ 进列表选择 + Enter 回填）"""
        if self.busy:
            return
        self.push_screen(HistoryModal(self._input._history),
                         callback=self._history_picked)

    def open_help_modal(self) -> None:
        """? / /help 帮助浮层（#39 品牌批 v4 化）"""
        if isinstance(self.screen, (HelpModal, HistoryModal, ApprovalModal)):
            return  # 已有浮层时不叠加
        self.push_screen(HelpModal())

    def _history_picked(self, text) -> None:
        if text:
            self._input.text = text
            self._input.move_cursor((0, len(text)))
            self.set_focus(self._input)

    # ———— renderer 状态 → widget 增量同步 ————

    def renderer_sync(self, stream_only: bool = False) -> None:
        """增量同步（renderer 状态变更统一入口，经 _post 线程安全）。
        stream_only = 流式快速路径（token/reasoning）：只刷流式三行 + 跟随滚动
        ——header/hint/observe/plan 签名比对防每 token 重建（性能审查：此前
        每 token 全量对账，长会话 O(n)/token 重演「抽搐」）。"""
        render = self.renderer
        if self._header_widget is None:
            return  # on_mount 前的早到消息（call_from_thread 队列）
        if stream_only:
            if self._block_count != len(render._blocks):
                return self.renderer_sync(False)  # 思考快照落块 → 升级全量对账
            self._sync_streams(render)
            self._follow_end()
            self.sync_hint()
            return
        self._block_count = len(render._blocks)
        self._sync_header(render)
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
                                b.get("content", ""), b.get("folded", False),
                                b.get("sender", "orchestrator"))
                self._blocks_container.mount(w, before=self._streams)
                self._content_version += 1
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
        if plan_active and self._plan_sig != id(render._plan_view):
            # 计划视图只在数据变化时重建（性能审查：此前每次 sync 重挂全部行，
            # 15s 观测轮询把用户看长计划的滚动位置重置）
            self._plan_sig = id(render._plan_view)
            self._build_plan()
        elif not plan_active:
            self._plan_sig = None
        self._sync_observe()
        # P1（D4 拍板仅 CC 窗口）：exec 形态开关（claude=执行时间线/其余气泡）
        exec_active = render._mode == "claude"
        if self._exec_sig != exec_active:
            self._exec_sig = exec_active
            self.set_class(exec_active, "exec-mode")
        self._follow_end()
        self.sync_hint()

    @property
    def _streams(self):
        return self.query_one("#streams", Vertical)

    def _sync_header(self, render) -> None:
        """状态栏：签名不变不重建（品牌对齐 #39 的 Text.assemble 每 token
        重拼是纯浪费——状态变化是离散事件）"""
        dot = render._agent_dot_tuple() if hasattr(render, "_agent_dot_tuple") else None
        pet = ""
        try:
            from agent.pet_events import last_state
            pet = last_state() or ""
        except Exception:
            pass
        sig = (render._mode, render._backend, render._session_id,
               render._cwd, dot, pet)
        if sig != self._header_sig:
            self._header_sig = sig
            self._header_widget.update(_header_text(render))

    def _at_end(self) -> bool:
        c = self._blocks_container
        return c.max_scroll_y - c.scroll_y < 2

    def _follow_end(self) -> None:
        """贴底跟随：内容版本变化（流式 flush/新块）且处于跟随态才滚（用户
        实测「结束停首页」根因：watch_scroll_y 把 reflow 抖动误判为用户滚动，
        跟随被误杀后 done 的最终 scroll 被跳过）。跟随态由 BlocksScroll 事件
        驱动维护（滚轮上滑/PgUp/拖拽上滑=暂停，滚回底部/End=恢复）"""
        if self._content_version == self._last_scroll_version:
            return
        if self._following:
            self._blocks_container.scroll_end(animate=False)
            self._last_scroll_version = self._content_version

    def _sync_streams(self, render) -> None:
        """流式区：执行中工具 / 思考 / 流式回答（身份标签 + 品牌色条气泡）。
        回答走 Markdown.append 增量解析（用户「不丝滑」根因之一：整文重解析
        每帧重建全部块）；思考行与回答同节流（monotonic 计时——审查修复：
        time.time() 遇 NTP 回拨会冻结流式显示）"""
        changed = False
        if render._working:
            self._stream_working.update(
                Text(f"⚙ {render._working} 执行中…", style="bold yellow"))
            self._stream_working.remove_class("hidden")
            changed = True
        elif not self._stream_working.has_class("hidden"):
            self._stream_working.add_class("hidden")
            changed = True
        if render._reasoning:
            now = time.monotonic()
            if (self._last_think_flush is None
                    or now - self._last_think_flush >= STREAM_FLUSH_INTERVAL):
                self._last_think_flush = now
                self._stream_thinking.update(
                    Text("思考中…\n" + render._reasoning, style="dim italic"))
                changed = True
            if self._stream_thinking.has_class("hidden"):
                self._stream_thinking.remove_class("hidden")
                changed = True
        else:
            self._last_think_flush = None
            if not self._stream_thinking.has_class("hidden"):
                self._stream_thinking.add_class("hidden")
                changed = True
        if render._answer:
            now = time.monotonic()
            if now - self._last_stream_flush >= STREAM_FLUSH_INTERVAL:
                self._last_stream_flush = now
                delta = render._answer[self._flushed_len:]
                if delta:
                    self._flushed_len = len(render._answer)
                    self._stream_answer.append(delta)  # 增量解析，diff 渲染
                    changed = True
            if self._stream_sender != render._sender:
                self._stream_sender = render._sender
                self._stream_answer_label.update(
                    _agent_label_text(render._sender))
            if self._stream_answer.has_class("hidden"):
                self._stream_answer.remove_class("hidden")
                changed = True
            if self._stream_answer_label.has_class("hidden"):
                # 首次显示也刷新（初始 sender 相同会跳过上面的比对——测试抓出）
                self._stream_answer_label.update(
                    _agent_label_text(render._sender))
                self._stream_answer_label.remove_class("hidden")
                changed = True
        else:
            self._last_stream_flush = 0.0
            self._flushed_len = 0
            if not self._stream_answer.has_class("hidden"):
                self._stream_answer.add_class("hidden")
                changed = True
            if not self._stream_answer_label.has_class("hidden"):
                self._stream_answer_label.add_class("hidden")
                changed = True
        if changed:
            self._content_version += 1

    def _build_plan(self) -> None:
        """计划队列视图（v3.2 #38 同内容：列表=状态词+进度条+计划消息，
        详情=步骤逐行；行口径与 terminal._plan_renderable 对齐）"""
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
            parts = [(f"[{i + 1}] ", "bold"), (title, ""), ("  ", ""),
                     (PLAN_ST_WORD.get(st, st), PLAN_ST_STYLE.get(st, "dim"))]
            msg = str(p.get("message") or "")[:30]
            if msg:
                parts += [("  ", ""), (msg, "dim")]  # 与 v3 rich 行口径一致
            plan.mount(Static(Text.assemble(*parts)))
            bar = ProgressBar(total=100, show_eta=False)
            bar.progress = prog
            plan.mount(bar)

    def _sync_observe(self) -> None:
        """观测右栏（v3.2 #38 同内容；行内容与 terminal._observe_panel 共用
        _observe_lines）。宽终端（≥72）且云端通道可用才显示——与 v3 同门槛。
        签名比对：数据只在 15s 轮询/usage 变化时重建（_observe/_usage 均为
        整体替换，身份比较即签名）。守卫：on_resize 先于 on_mount。"""
        if self._observe_widget is None:
            return
        render = self.renderer
        visible = render._observe_ready and self.size.width >= 72
        sig = (render._observe, render._usage, visible)
        if sig != self._observe_sig:
            self._observe_sig = sig
            self._observe_widget.update(
                Text.assemble(*(Text(t, style=s) for t, s in _observe_lines(render))))
        self._observe_box.set_class(visible, "show")

    def sync_hint(self, stream_only: bool = False) -> None:
        """输入 dock 上方提示行（v3 ptk bottom_toolbar 同内容 + 忙态）。
        签名比对：内容只随 busy/选中/计划/临时提示变化"""
        render = self.renderer
        if self._hintbar is None:
            return
        flash_active = self._flash_until > time.monotonic()
        sig = (self.busy, flash_active, render._plan_view is not None, render.sel)
        if sig == self._hint_sig:
            return
        self._hint_sig = sig
        # flash 优先于 busy（生成中 Enter 的提示必须可见——用户实测反馈）
        if flash_active:
            text = Text(self._flash_text, style="cyan")
        elif self.busy:
            text = Text("生成中…（Ctrl+C 停止）", style="bold yellow")
        elif render._plan_view is not None:
            text = Text("计划视图 — Esc/Enter 返回对话流 | " + _HINT_BASE)
        elif render.sel is not None:
            b = render._blocks[render.sel]
            text = Text.assemble(
                ("已选中: " + b.get("title", ""), "bold"),
                (f" — Enter 展开/折叠 · Esc 取消 | {_HINT_BASE}", ""))
        else:
            # 用户实测「这终端好乱」：空闲态默认不显示按键提示（CC 同款零
            # 噪音）——按键速查进 ? 帮助浮层；有上下文时才显示
            self._hintbar.update("")
            self._hintbar.add_class("hidden")
            return
        self._hintbar.remove_class("hidden")
        self._hintbar.update(text)

    def flash_hint(self, text: str, seconds: float = 3.0) -> None:
        """临时提示（Tab 补全候选等）：定时器到期自动回落常规提示（审查修复：
        此前无定时器，idle 时过期提示滞留到下一次无关 sync）"""
        self._flash_text = text
        self._flash_until = time.monotonic() + seconds
        self._hint_sig = None  # 强制下一次 sync_hint 重画
        self.sync_hint()
        if self._flash_timer is not None:
            self._flash_timer.stop()
        self._flash_timer = self.set_timer(seconds, self._on_flash_expire)

    def _on_flash_expire(self) -> None:
        self._flash_until = 0.0
        self._flash_timer = None
        self._hint_sig = None
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
        self._sender = "orchestrator"  # 当前说话人（气泡身份标签，网页同款）

    # ———— App 生命周期 ————

    def attach(self, app) -> None:
        self._app = app

    def detach(self) -> None:
        self._app = None

    def is_attached(self) -> bool:
        return self._app is not None

    # ———— T2 品牌对齐（2026-11-18）：主题应用/读取（/theme 命令经
    #     dispatch_command 鸭子调用；App 主题变更只走这里） ————

    def set_theme(self, theme: str) -> None:
        app = getattr(self, "_app", None)
        if app is not None:
            app.apply_theme(theme)

    def current_theme(self) -> str:
        app = getattr(self, "_app", None)
        if app is None:
            return "dark"
        return "dark" if app.current_theme.dark else "light"

    def _agent_dot_tuple(self) -> tuple:
        from agent.terminal import _agent_dot_tuple
        return _agent_dot_tuple(self)

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

    def _notify(self, scope: str = None) -> None:
        """状态已变 → 通知 App 增量同步。调用来源分两路：
        - App 事件循环线程（查询协程/回合任务）= 直接同步调用
        - 其他线程（观测轮询 daemon / claude_loop executor）= call_from_thread
          投递消息，队列 FIFO 保序、线程安全
        scope='stream' = 流式增量（token/reasoning）——App 走快速路径只刷
        流式三行（性能审查修复）。detach/未 attach 静默 no-op。"""
        app = self._app
        if app is not None:
            self._post(app.renderer_sync, scope == "stream")

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

    def set_sender(self, sender: str) -> None:
        """当前说话人（气泡身份标签，网页 MessageBubble 同款）：
        run_claude_query 设 claude（棕色标签）、云端/本地 LLM 默认统筹"""
        self._sender = sender or "orchestrator"
        self._notify()

    def load_history(self, messages: list, default_sender: str = "orchestrator") -> None:
        """会话历史 → 块（/sessions 切换、/chat 进入与本机续接时用）；
        映射逻辑与 FullscreenRenderer 共用 history_to_blocks。
        default_sender：本机 /claude 会话续接传 claude（历史标 Claude 标签）"""
        self._blocks = history_to_blocks(messages, default_sender)
        self.sel = None
        self._notify()

    def clear_blocks(self) -> None:
        """清空全部对话块（/clear 命令；与 FullscreenRenderer 同接口）"""
        self._blocks.clear()
        self.sel = None
        self._notify()

    def add_user_message(self, content: str) -> None:
        """自己发的消息立即上屏（用户实测「看不到我发的消息」——网页同款
        即时反馈：发送即见右对齐蓝底气泡）"""
        self._blocks.append({"kind": "user", "title": "", "content": content,
                             "folded": False, "sender": "orchestrator"})
        self._notify()

    def merge_remote_messages(self, messages: list) -> None:
        """对端设备新消息尾部合入（愿景 P0 2026-11-15 消息同步闭环）：按
        msg_id 去重；只追加不缩减。轮询线程调用——_notify 跨线程投递安全"""
        blocks = history_to_blocks(messages)
        existing_ids = {b.get("msg_id") for b in self._blocks if b.get("msg_id")}
        for b in blocks:
            mid = b.get("msg_id")
            if mid and mid in existing_ids:
                continue
            self._blocks.append(b)
        self._notify()

    def redraw(self) -> None:
        """全量同步（Textual 增量渲染——等价重绘，实际只动变化 widget）"""
        self._notify()

    def show_help(self) -> None:
        """? 帮助浮层（/help 命令在 v4 走 modal 而非 info 块——CC 同款）"""
        if self._app is not None:
            self._post(self._app.open_help_modal)

    def set_usage(self, total: int, cached: int = 0) -> None:
        """上轮 token 消耗（usage_event，run_cloud_query 消费）"""
        self._usage = {"total": int(total or 0), "cached": int(cached or 0)}
        self._notify()

    def tick_observation(self, data: dict) -> None:
        """观测轮询线程注入（15s /chat/cc-activity）：只更新状态；渲染时机
        由 _post 投递——Textual 刷新线程安全，无需 v3 的 _prompt_active 守卫"""
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
                             "content": self._reasoning, "folded": True,
                             "sender": self._sender})
        self._reasoning = ""
        self._think_start = None

    def token(self, text: str) -> None:
        if self._reasoning:  # 首个回答 token：剩余思考存为「最终思考」（网页同款）
            self._snapshot_thinking(final=True)  # 可能落块——App stream 快速
            # 路径会校验块数变化自动升级全量对账
        self._answer += text
        self._notify(scope="stream")

    def reasoning(self, text: str) -> None:
        if self._think_start is None:
            self._think_start = time.time()
        self._reasoning += text
        self._notify(scope="stream")

    def tool_start(self, name: str) -> None:
        self._tool_count += 1  # 先计数：思考块标题「N 次工具调用」含本次
        self._snapshot_thinking()
        self._working = name
        self._notify()

    def tool_end(self, name: str, output: str) -> None:
        self._blocks.append({"kind": "tool", "title": f"⚙ {name}",
                             "content": _truncate_tool_output(output),
                             "folded": True, "sender": self._sender})
        self._working = None
        self._notify()

    def done(self) -> None:
        self._snapshot_thinking(final=True)
        if self._answer:
            self._blocks.append({"kind": "answer", "title": "",
                                 "content": self._answer, "folded": False,
                                 "sender": self._sender})
            self._answer = ""
        self._working = None
        self._notify()

    def error(self, text: str) -> None:
        # 审查修复：清流式残留——v3 的 redraw 只画块，Textual 的流式行是
        # 常驻 widget，不清会永久显示「⚙ X 执行中…/思考中…」
        # 补漏扫描：_answer 也清——否则失败轮次的半截回答残留流式行且会
        # 拼进下一轮 done() 的回答块
        self._working = None
        self._reasoning = ""
        self._think_start = None
        self._answer = ""
        self._blocks.append({"kind": "error", "title": "", "content": text,
                             "folded": False, "sender": self._sender})
        self._notify()

    def info(self, text: str) -> None:
        self._blocks.append({"kind": "info", "title": "", "content": text,
                             "folded": False, "sender": self._sender})
        self._notify()

    def interrupted(self) -> None:
        self._answer = ""
        self._working = None
        self._reasoning = ""
        self._think_start = None
        self._blocks.append({"kind": "info", "title": "", "content": "（已停止生成）",
                             "folded": False, "sender": self._sender})
        self._notify()

    # ———— 审批（v4 modal 形态；v3 语义不变：120s 超时默认 deny） ————

    async def approve_async(self, tool_name: str, command: str) -> str:
        """云端通道审批（run_cloud_query 在回合任务内 await）：推 modal →
        等决议；超时默认 deny 并收起 modal。CancelledError（Ctrl+C 停止）也
        收起 modal 后重抛（审查修复：except Exception 漏 BaseException，
        modal 会滞留屏幕）"""
        if self._app is None:
            return "deny"
        _emit_pet("attention")
        fut = asyncio.get_running_loop().create_future()
        self._post(self._app.push_approval, tool_name, command, fut)
        try:
            ok = await asyncio.wait_for(fut, timeout=120)
            return "approve" if ok else "deny"
        except asyncio.CancelledError:
            self._post(self._app.dismiss_approval)
            raise
        except Exception:
            self._post(self._app.dismiss_approval)
            return "deny"

    def approve_blocking(self, decision_id: str, tool_name: str, command: str) -> str:
        """本机 /claude 审批（claude_loop 经 executor 线程同步阻塞调用）：
        推 modal → 阻塞等决议；超时默认 deny 并收起 modal。"""
        if self._app is None:
            return "deny"
        _emit_pet("attention")
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
    回退 v3 ptk 路径——降级链保留）。本地终端第三端（用户拍板
    2026-11-15）：启动即接续云端窗口（claude=网站 CC 窗口 / chat=小元主
    对话，与网站完全同步）；云端不可达静默回退本地历史。观测轮询与 v3 同源
    （15s /chat/cc-activity）；客户端注入 ctx。App 自带 alt-screen。"""
    from agent.terminal import _make_cloud_client, _start_sync_poll
    # D1 拍板（2026-11-15）：启动永远接续网站 CC 窗口（/local 需手动进入）
    mode = "claude"
    app = YuanTerminalApp(session, store, render)
    client = _make_cloud_client()
    if client is not None:
        app.ctx.cloud_client = client  # 与 v3 run_repl 同口径（/status 可见已连接）
        _wire_observe(render, client)
        try:
            loop = asyncio.get_running_loop()
            sessions = await loop.run_in_executor(
                None, client.list_sessions, "claude")
            sid = (str(sessions[0].get("session_id", "")) if sessions
                   else await loop.run_in_executor(
                       None, client.create_session, "claude"))
            msgs = await loop.run_in_executor(
                None, client.load_messages, sid)
            app.resume = {"mode": mode, "sid": sid, "messages": msgs}
        except Exception:
            app.resume = None  # 云端不可达：on_mount 回退本地历史
        # 愿景 P0（2026-11-15 消息同步闭环）：15s 增量轮询——网站发的消息
        # 终端实时上屏（进行中回合跳过，不打断本地流式）
        _start_sync_poll(render, lambda: client,
                         lambda: (app.ctx.cloud_sid, app.busy))
    try:
        await app.run_async()
    finally:
        render.detach()  # 轮询线程持旧 render 引用——detach 后 _post no-op 且
        # 轮询循环经 is_attached() 检查退出（审查修复：回退路径轮询线程泄漏）
    if getattr(app, "return_code", 0) not in (0, None):
        # Textual 内部捕获了驱动/handler 异常（run_async 正常返回但 return_code
        # 非零）——抛给 run_repl 走 v3 回退（审查修复：此前静默吞掉，yuan
        # 直接死掉而非降级）
        raise RuntimeError(f"Textual 运行失败（return_code={app.return_code}）")
