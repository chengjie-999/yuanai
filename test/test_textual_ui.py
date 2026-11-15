"""终端 TUI v4 Textual 渲染层测试（2026-11-15 拍板，决策点 A）。

分层：
- 渲染器状态测试（detached 纯状态，不跑 App）：流式接口块语义与 v3 对齐
- App 交互测试（Textual run_test 无头驱动 + pilot 按键）：挂载/提交/选择/
  折叠/计划视图/观测右栏/审批 modal/停止语义/退出
- 回退链测试：run_textual_repl 失败 → run_repl 回退 v3 ptk 路径

隔离纪律（#38 教训）：App 测试经 run_test 无头驱动（不碰真实控制台）；
HISTORY_FILE/会话文件全部 monkeypatch 到 tmp_path；不触发真实网络。
"""

import asyncio
from pathlib import Path
import os
import threading

from agent.terminal import MAX_TOOL_OUTPUT, TerminalSessionStore
from agent.textual_ui import (ApprovalModal, TextualRenderer, YuanTerminalApp)

os.environ["TERMINAL_DARK"] = "1"


def _make_app(tmp_path, size=(100, 40)):
    store = TerminalSessionStore(path=str(tmp_path / "sessions.json"))
    s = store.new_session("claude")
    render = TextualRenderer(cwd="C:/test", session_id=s["id"])
    app = YuanTerminalApp(s, store, render)
    return store, s, render, app, size


def _run(coro):
    asyncio.run(coro)


# ==================== 渲染器状态（detached，无 App） ====================


def test_stream_blocks_state_matches_v3():
    """流式接口 → 块状态与 v3 FullscreenRenderer 同语义：
    思考快照折叠挂工具上方、工具折叠、回答展开"""
    r = TextualRenderer(cwd="C:/x", session_id="s1")
    r.reasoning("先想一下")
    r.tool_start("bash")
    assert r._working == "bash"
    assert r._blocks[0]["kind"] == "thinking"
    assert r._blocks[0]["folded"] is True
    assert "1 次工具调用" in r._blocks[0]["title"]
    r.tool_end("bash", "git status 输出")
    assert r._working is None
    assert r._blocks[-1]["kind"] == "tool"
    assert r._blocks[-1]["folded"] is True
    assert r._blocks[-1]["title"] == "⚙ bash"
    r.token("你好，**世界**")
    r.done()
    assert r._blocks[-1]["kind"] == "answer"
    assert r._blocks[-1]["folded"] is False
    assert r._blocks[-1]["content"] == "你好，**世界**"
    assert r._answer == ""


def test_final_thinking_snapshot_on_first_token():
    """首个回答 token：剩余思考存「最终思考」折叠块（网页同款）"""
    r = TextualRenderer()
    r.reasoning("收尾思考")
    r.token("回答开始")
    kinds = [b["kind"] for b in r._blocks]
    assert kinds == ["thinking"]
    assert "最终思考" in r._blocks[0]["title"]
    assert r._blocks[0]["folded"] is True
    assert r._reasoning == ""


def test_info_error_interrupted_blocks():
    r = TextualRenderer()
    r.info("提示")
    r.error("失败")
    r._answer = "半截答案"
    r.interrupted()
    kinds = [(b["kind"], b["content"]) for b in r._blocks]
    assert kinds == [("info", "提示"), ("error", "失败"),
                     ("info", "（已停止生成）")]
    assert r._answer == ""


def test_tool_output_truncation():
    r = TextualRenderer()
    r.tool_end("bash", "x" * (MAX_TOOL_OUTPUT + 100))
    out = r._blocks[-1]["content"]
    assert len(out) < len("x" * (MAX_TOOL_OUTPUT + 100))
    assert "输出过长已截断" in out


def test_load_history_mapping_and_clear():
    r = TextualRenderer()
    r.load_history([
        {"role": "user", "content": "问题"},
        {"role": "assistant", "content": "回答"},
        {"role": "system", "content": "跳过"},
        {"role": "assistant", "content": "   "},
    ])
    assert [(b["kind"], b["content"]) for b in r._blocks] == [
        ("user", "问题"), ("answer", "回答")]
    r.clear_blocks()
    assert r._blocks == []
    assert r.sel is None


def test_plan_view_state_and_toggle_fold():
    r = TextualRenderer()
    r.show_plans([{"title": "计划A", "status": "running", "progress": 40}])
    assert r._plan_view is not None
    assert r._plan_view["plans"][0]["title"] == "计划A"
    r.set_plan_view(None)
    assert r._plan_view is None
    r._blocks = [{"kind": "tool", "title": "⚙ bash", "content": "x",
                  "folded": True}]
    r.toggle_fold(0)
    assert r._blocks[0]["folded"] is False
    r._blocks = [{"kind": "answer", "title": "", "content": "x", "folded": False}]
    r.toggle_fold(0)  # answer 不折叠
    assert r._blocks[0]["folded"] is False


def test_approve_detached_fail_closed():
    r = TextualRenderer()
    assert r.approve_blocking("d", "bash", "x") == "deny"
    _run(_assert_detached_approve_async_deny(r))


async def _assert_detached_approve_async_deny(r):
    assert await r.approve_async("bash", "x") == "deny"


# ==================== App 挂载与交互（run_test + pilot） ====================


def _run_app_test(coro_fn, tmp_path, monkeypatch, size=(100, 40)):
    monkeypatch.setattr("agent.textual_ui.HISTORY_FILE",
                        str(tmp_path / "history.txt"))
    monkeypatch.setattr("agent.terminal.HISTORY_FILE",
                        str(tmp_path / "history.txt"))

    async def _wrap():
        store, s, render, app, sz = _make_app(tmp_path, size=size)
        async with app.run_test(size=sz) as pilot:
            await coro_fn(pilot, app, render, s, store)
    _run(_wrap())


def test_app_mount_header_focus_and_brand(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        await pilot.pause()
        header = app.query_one("#header")
        assert "小元AI" in header.render().plain  # 品牌对齐 #39
        assert isinstance(app.focused, type(app.query_one("#input")))
        assert len(app.query("BlockWidget")) == 0
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_submit_help_shows_info_block(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        app.query_one("#input").text = "/help"
        await pilot.press("enter")
        await pilot.pause()
        blocks = list(app.query("BlockWidget"))
        assert len(blocks) == 1
        assert blocks[0].block_kind == "info"
        assert "命令" in blocks[0].block_content
        assert app.query_one("#input").text == ""  # 提交即清空
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_up_down_select_enter_fold_escape(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        render.tool_end("bash", "输出")
        render.info("尾部块")
        await pilot.pause()
        await pilot.press("up")  # 从未选中 → 选中最后一块（info）
        assert render.sel == len(render._blocks) - 1
        await pilot.press("up")
        assert render.sel == len(render._blocks) - 2  # 上一块（tool）
        await pilot.press("enter")  # tool 折叠展开
        assert render._blocks[render.sel]["folded"] is False
        await pilot.press("enter")
        assert render._blocks[render.sel]["folded"] is True
        await pilot.press("escape")
        assert render.sel is None
        await pilot.press("down")  # sel None → 保持 None（v3 同语义）
        assert render.sel is None
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_plan_view_toggle_and_enter_exit(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        render.show_plans([{"title": "数据分析", "status": "running",
                            "progress": 40, "done_steps": 2, "total_steps": 5}])
        await pilot.pause()
        assert app.query_one("#plan").has_class("show")
        assert app.query_one("#blocks").has_class("hidden")
        inp = app.query_one("#input")
        inp.text = "/status"
        await pilot.press("enter")  # 计划视图 Enter = 退出视图（输入保留）
        await pilot.pause()
        assert render._plan_view is None
        assert app.query_one("#plan").has_class("show") is False
        assert inp.text == "/status"  # 未提交，缓冲保留（v3 pending_input 同款）
        # 再 Enter 才真正提交命令
        await pilot.press("enter")
        await pilot.pause()
        assert any(b.block_kind == "info" and "本机 Agent" in b.block_content
                   for b in app.query("BlockWidget"))
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_observe_panel_width_gate(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        render._observe_ready = True
        render.tick_observation({"online": True, "age_s": 5,
                                 "latest": {"message": "跑分析", "ts": 0},
                                 "activities": [{"message": "跑分析", "ts": 0}]})
        await pilot.pause()
        assert app.query_one("#observe").has_class("show")
        assert "活跃" in app.query_one("#observe-content").render().plain
    _run_app_test(body, tmp_path, monkeypatch, size=(100, 40))


def test_app_observe_hidden_on_narrow_terminal(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        render._observe_ready = True
        render.tick_observation({"online": True, "age_s": None,
                                 "latest": None, "activities": []})
        await pilot.pause()
        assert not app.query_one("#observe").has_class("show")  # 宽 <72 降级
    _run_app_test(body, tmp_path, monkeypatch, size=(60, 20))


def test_app_observe_error_state(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        render._observe_ready = True
        render.tick_observation({"error": True})
        await pilot.pause()
        assert "云端不可用" in app.query_one("#observe-content").render().plain
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_approval_modal_async_y_and_n(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        async def ask():
            return await render.approve_async("bash", "git push")
        task = asyncio.create_task(ask())
        await pilot.pause()
        assert isinstance(app.screen, ApprovalModal)
        await pilot.press("y")
        assert await task == "approve"
        task2 = asyncio.create_task(ask())
        await pilot.pause()
        await pilot.press("n")
        assert await task2 == "deny"
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_approval_blocking_from_executor_thread(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        result = {}

        def blocking():
            result["r"] = render.approve_blocking("d1", "bash", "rm x")
        t = threading.Thread(target=blocking)
        t.start()
        await pilot.pause()
        assert isinstance(app.screen, ApprovalModal)
        await pilot.press("n")
        t.join(10)
        assert not t.is_alive()
        assert result["r"] == "deny"
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_busy_guard_ignores_enter(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        app._busy_task = object()  # busy 为派生属性（无 setter）
        inp = app.query_one("#input")
        inp.text = "/help"
        await pilot.press("enter")
        await pilot.pause()
        assert inp.text == "/help"  # 生成中不消费输入
        assert len(app.query("BlockWidget")) == 0
        app._busy_task = None
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_ctrl_c_stops_real_submit_turn(tmp_path, monkeypatch):
    """审查回归（真实提交链路）：回合在独立任务跑、消息泵不被阻塞——Ctrl+C
    生成中即停不退出。此前回合整段 await 在消息 handler 内：泵被阻塞，Ctrl+C
    排队到回合结束后按空闲分支退出整个终端（旧测试用合成任务掩盖了真实泵模型）"""
    async def body(pilot, app, render, s, store):
        cancelled = {}
        started = threading.Event()

        async def slow_turn(line, ctx, rich_mode=True):
            started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled["yes"] = True
                raise
            return ""

        monkeypatch.setattr("agent.textual_ui.run_turn", slow_turn)
        inp = app.query_one("#input")
        inp.text = "帮我写代码"
        await pilot.press("enter")
        for _ in range(200):
            if started.is_set():
                break
            await asyncio.sleep(0.01)
        assert started.is_set()
        assert app.busy is True
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert cancelled.get("yes") is True  # 回合任务被取消
        assert not app._exit  # 停止生成不退出
        assert app.busy is False  # finally 清理
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_ctrl_c_idle_exits(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app._exit
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_quit_command_exits(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        app.query_one("#input").text = "/quit"
        await pilot.press("enter")
        await pilot.pause()
        assert app._exit
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_tab_completes_slash_command(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        inp = app.query_one("#input")
        inp.text = "/pl"
        await pilot.press("tab")
        await pilot.pause()
        assert inp.text == "/plan"  # 唯一前缀补全
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_submit_remembers_history(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        inp = app.query_one("#input")
        inp.text = "/help"
        await pilot.press("enter")
        await pilot.pause()
        with open(str(tmp_path / "history.txt"), encoding="utf-8") as f:
            assert "/help" in f.read()
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_click_block_title_toggles_fold(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        render.tool_end("bash", "输出")
        await pilot.pause()
        assert render._blocks[0]["folded"] is True
        title = app.query("BlockWidget").first().query(".btitle").first()
        await pilot.click(title)
        await pilot.pause()
        assert render._blocks[0]["folded"] is False  # 点标题行展开
        await pilot.click(title)
        await pilot.pause()
        assert render._blocks[0]["folded"] is True  # 再点折回
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_clear_command_clears_blocks(tmp_path, monkeypatch):
    async def body(pilot, app, render, s, store):
        render.info("块一")
        await pilot.pause()
        assert len(app.query("BlockWidget")) == 1
        app.query_one("#input").text = "/clear"
        await pilot.press("enter")
        await pilot.pause()
        assert len(app.query("BlockWidget")) == 1  # 「当前会话已清空」info
        assert app.query("BlockWidget").first().block_content.startswith("当前会话已清空")
        assert render._blocks[-1]["kind"] == "info"
    _run_app_test(body, tmp_path, monkeypatch)


# ==================== 审查修复回归（2026-11-15 五角度审查批次） ====================


def test_app_esc_armed_disarmed_by_typing(tmp_path, monkeypatch):
    """审查修复：Esc 武装不解除曾致 Esc 后首次 Enter 误插换行不提交"""
    async def body(pilot, app, render, s, store):
        await pilot.press("escape", "slash", "h", "e", "l", "p", "enter")
        await pilot.pause()
        blocks = list(app.query("BlockWidget"))
        assert len(blocks) == 1 and blocks[0].block_kind == "info"  # 正常提交了
        assert app.query_one("#input").text == ""
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_enter_selected_nonfoldable_does_not_submit(tmp_path, monkeypatch):
    """审查修复：选中非折叠块时 Enter 曾把半写消息发给模型（v3 只刷新不提交）"""
    async def body(pilot, app, render, s, store):
        render.info("提示块")
        await pilot.pause()
        await pilot.press("up")  # 选中 info 块
        assert render.sel == 0
        inp = app.query_one("#input")
        inp.text = "/help"
        await pilot.press("enter")
        await pilot.pause()
        assert inp.text == "/help"  # 未提交，输入保留
        assert render.sel == 0
        assert len(list(app.query("BlockWidget"))) == 1  # 无新块
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_tab_completion_cursor_stays_at_end(tmp_path, monkeypatch):
    """审查修复：Tab 补全走 load_text 光标回 0 位——后续输入曾插到命令前"""
    async def body(pilot, app, render, s, store):
        inp = app.query_one("#input")
        inp.text = "/pl"
        await pilot.press("tab")
        await pilot.pause()
        assert inp.text == "/plan"
        inp.insert(" 3")
        await pilot.pause()
        assert inp.text == "/plan 3"
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_approval_default_focus_is_deny(tmp_path, monkeypatch):
    """审查修复：modal 曾自动聚焦「执行」按钮——回车即批准，与 v3 [y/N]
    fail-closed 语义相反"""
    async def body(pilot, app, render, s, store):
        async def ask():
            return await render.approve_async("bash", "git push")
        task = asyncio.create_task(ask())
        await pilot.pause()
        assert isinstance(app.screen, ApprovalModal)
        assert app.focused is app.screen.query_one("#approve-no")
        await pilot.press("enter")
        assert await task == "deny"
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_interrupt_dismisses_approval_modal(tmp_path, monkeypatch):
    """审查修复：CancelledError 不过 except Exception——停止时收起审批卡防滞留"""
    async def body(pilot, app, render, s, store):
        async def ask():
            return await render.approve_async("bash", "rm x")
        app._busy_task = asyncio.create_task(ask())
        await pilot.pause()
        assert isinstance(app.screen, ApprovalModal)
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert not isinstance(app.screen, ApprovalModal)
        try:
            await app._busy_task
        except asyncio.CancelledError:
            pass
        app._busy_task = None
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_interrupted_clears_stream_indicators(tmp_path, monkeypatch):
    """审查修复：停止/出错曾残留「⚙ X 执行中…/思考中…」流式行"""
    async def body(pilot, app, render, s, store):
        render.tool_start("bash")
        render.reasoning("在想")
        await pilot.pause()
        assert not app._stream_working.has_class("hidden")
        assert not app._stream_thinking.has_class("hidden")
        render.interrupted()
        await pilot.pause()
        assert app._stream_working.has_class("hidden")
        assert app._stream_thinking.has_class("hidden")
        assert app._stream_answer.has_class("hidden")
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_history_file_ptk_compatible(tmp_path, monkeypatch):
    """审查修复（CLAUDE.md 教训 #3 单一写路径）：历史文件与 v3 ptk FileHistory
    同格式——v4 输入在 v3 回退路径的 ↑ 历史里必须可读"""
    async def body(pilot, app, render, s, store):
        app.query_one("#input").text = "/help"
        await pilot.press("enter")
        await pilot.pause()
        from prompt_toolkit.history import FileHistory
        items = FileHistory(str(tmp_path / "history.txt")).load_history_strings()
        assert "/help" in items
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_ctrl_r_history_modal_backfills_input(tmp_path, monkeypatch):
    """Ctrl+R 历史（v4 形态：列表回填——/help 文案键位对齐）"""
    async def body(pilot, app, render, s, store):
        inp = app.query_one("#input")
        inp.text = "/help"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("ctrl+r")
        await pilot.pause()
        from agent.textual_ui import HistoryModal
        assert isinstance(app.screen, HistoryModal)
        await pilot.press("enter")  # 选中第一项（最近）
        await pilot.pause()
        assert inp.text == "/help"
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_plan_view_pagedown_scrolls_plan(tmp_path, monkeypatch):
    """审查修复：PgUp/PgDn 曾恒滚块流容器——计划视图键盘翻页失效"""
    async def body(pilot, app, render, s, store):
        steps = [{"step_no": i, "skill": "analysis", "desc": f"步骤{i}",
                  "status": "pending"} for i in range(1, 40)]
        render.show_plans([], detail={"title": "长计划", "status": "running",
                                      "progress": 10, "steps": steps,
                                      "done_steps": 1, "total_steps": 39})
        await pilot.pause()
        assert render._plan_view is not None
        assert app._plan_container.max_scroll_y > 0
        await pilot.press("pagedown")
        await pilot.pause()
        assert app._plan_container.scroll_y > 0
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_stream_scope_upgrades_when_snapshot_blocks(tmp_path, monkeypatch):
    """流式快速路径块数校验：首个 token 快照「最终思考」落块 → 自动升级全量对账"""
    async def body(pilot, app, render, s, store):
        render.reasoning("先想")
        render.token("答")
        await pilot.pause()
        kinds = [w.block_kind for w in app.query("BlockWidget")]
        assert kinds == ["thinking"]
    _run_app_test(body, tmp_path, monkeypatch)


# ==================== 展示层修复回归（网页端气泡形态，2026-11-15 用户实测） ====================


def test_app_user_block_right_aligned_blue_bubble(tmp_path, monkeypatch):
    """用户消息 = 右对齐品牌蓝底白字气泡（网页 MessageBubble 同款）——
    用户实测「混在模型输出里分辨不了」"""
    async def body(pilot, app, render, s, store):
        store.append(s["id"], "user", "我的问题", "claude")
        render._blocks.append({"kind": "user", "title": "", "content": "我的问题",
                               "folded": False, "sender": "orchestrator"})
        render._notify()
        await pilot.pause()
        w = app.query("BlockWidget.user-block").first()
        assert w is not None
        bubble = w.query(".ububble").first()
        assert "我的问题" in bubble.render().plain
        from textual.color import Color
        # 蓝底白字（网页 var(--accent) + #fff 同款）
        assert bubble.styles.background == Color(1, 120, 212)  # $primary 品牌蓝
        assert bubble.styles.color == Color(255, 255, 255)
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_answer_block_has_label_and_color_bar(tmp_path, monkeypatch):
    """模型输出 = 左对齐气泡 + 身份标签行（色点+名称+AI 徽标）+ 品牌色条"""
    async def body(pilot, app, render, s, store):
        render.done() if False else None
        render._blocks.append({"kind": "answer", "title": "",
                               "content": "回答正文", "folded": False,
                               "sender": "orchestrator"})
        render._notify()
        await pilot.pause()
        w = app.query("BlockWidget.answer-block").first()
        label = w.query(".alabel").first()
        assert "小元AI" in label.render().plain
        assert "AI" in label.render().plain
        assert "回答正文" in w.query(".abubble").first().source  # Markdown render() 恒 Blank
    _run_app_test(body, tmp_path, monkeypatch)


def test_renderer_blocks_stamped_with_sender():
    """块带说话人戳记：/claude 轮次的回答块标记 claude（棕色标签）"""
    r = TextualRenderer()
    r.set_sender("claude")
    r.token("回答")
    r.done()
    assert r._blocks[-1]["sender"] == "claude"
    r.set_sender("orchestrator")
    r.token("统筹回答")
    r.done()
    assert r._blocks[-1]["sender"] == "orchestrator"


def test_renderer_history_blocks_carry_sender():
    """云端历史 sender 透传（网页多智能体身份标签同款）"""
    r = TextualRenderer()
    r.load_history([
        {"role": "user", "content": "问题"},
        {"role": "assistant", "content": "回答", "sender": "claude"},
    ])
    assert r._blocks[1]["sender"] == "claude"


def test_app_stream_answer_shows_label_and_bubble(tmp_path, monkeypatch):
    """流式回答同样带身份标签 + 气泡样式（生成中即可分辨说话人）"""
    async def body(pilot, app, render, s, store):
        render.token("流式回答")
        await pilot.pause()
        label = app._stream_answer_label
        assert not label.has_class("hidden")
        assert "小元AI" in label.render().plain
        assert "流式回答" in app._stream_answer.source
    _run_app_test(body, tmp_path, monkeypatch)


def test_repl_context_shares_mode_ref_list(tmp_path):
    """审查修复：ReplContext 曾自建 mode_ref 列表——ptk 提示符闭包读旧列表，
    /chat /claude 后提示符冻结旧模式"""
    from agent.terminal import ReplContext
    store = TerminalSessionStore(path=str(tmp_path / "s.json"))
    s = store.new_session("claude")
    mode_ref = ["claude"]
    ctx = ReplContext(s, store, None, mode_ref)
    ctx.mode_ref[0] = "cloud"
    assert mode_ref[0] == "cloud"  # 同一列表（prompt_fn 闭包同步可见）


# ==================== 补漏扫描修复回归（2026-11-15 Phase 3 sweep） ====================


def test_app_follow_pauses_on_user_scroll_up(tmp_path, monkeypatch):
    """用户实测「结束停首页/滚轮失灵」根因修复：跟随态改事件驱动——
    watch_scroll_y 曾把 reflow 抖动误判为用户滚动（跟随被误杀、流式 flush
    把滚轮拉回底部）。滚轮上滑=暂停、滚回底部=恢复"""
    async def body(pilot, app, render, s, store):
        from textual.events import MouseScrollUp, MouseScrollDown
        for i in range(40):
            render.info(f"填充块 {i}")  # 造出可滚动内容
        await pilot.pause()
        blocks = app._blocks_container
        blocks.scroll_end(animate=False)
        await pilot.pause()
        assert blocks.max_scroll_y > 0
        assert app._following is True  # 初始跟随
        blocks.post_message(MouseScrollUp(None, 50.0, 20.0, 0, 3, 0, False, False, False))
        await pilot.pause()
        assert app._following is False  # 滚轮上滑 = 暂停跟随
        blocks.post_message(MouseScrollDown(None, 50.0, 20.0, 0, -3, 0, False, False, False))
        await pilot.pause()
        await pilot.pause()  # call_after_refresh 回底判定落位
        assert app._following is True  # 滚回底部恢复
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_reflow_does_not_kill_follow(tmp_path, monkeypatch):
    """reflow 引起的 scroll_y 变化（无 grabbed 标记）不得误判为用户滚动——
    用户实测「输出结束停在首页」的直接根因"""
    async def body(pilot, app, render, s, store):
        for i in range(40):
            render.info(f"填充块 {i}")
        await pilot.pause()
        blocks = app._blocks_container
        blocks.scroll_end(animate=False)
        await pilot.pause()
        assert app._following is True
        blocks.scroll_y = 1  # 模拟 reflow/程序滚动（非 grabbed 非滚轮事件）
        await pilot.pause()
        assert app._following is True  # 不误判
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_pgup_pauses_follow_end_resumes(tmp_path, monkeypatch):
    """键盘翻页同滚轮语义：PgUp 暂停跟随、End 回底恢复"""
    async def body(pilot, app, render, s, store):
        for i in range(40):
            render.info(f"填充块 {i}")
        await pilot.pause()
        blocks = app._blocks_container
        blocks.scroll_end(animate=False)
        await pilot.pause()
        assert app._following is True
        await pilot.press("pageup")
        assert app._following is False
        await pilot.press("end")
        assert app._following is True
    _run_app_test(body, tmp_path, monkeypatch)


def test_renderer_error_clears_answer():
    """补漏扫描：error 曾不清 _answer——失败轮次半截回答会拼进下一轮回答块"""
    r = TextualRenderer()
    r.token("前半段")
    r.error("连接失败")
    assert r._answer == ""
    r.token("新一轮")
    r.done()
    assert r._blocks[-1]["content"] == "新一轮"


def test_app_dismiss_approval_resolves_blocking_thread(tmp_path, monkeypatch):
    """补漏扫描：dismiss_approval 曾只弹屏不决议——executor 线程阻塞到
    120s 超时，asyncio.run 关停等待致进程假死"""
    async def body(pilot, app, render, s, store):
        result = {}

        def blocking():
            result["r"] = render.approve_blocking("d1", "bash", "rm x")
        t = threading.Thread(target=blocking)
        t.start()
        await pilot.pause()
        assert isinstance(app.screen, ApprovalModal)
        busy_task = asyncio.create_task(asyncio.sleep(30))  # 模拟生成中任务
        app._busy_task = busy_task
        await pilot.press("ctrl+c")  # 停止 → 收起审批卡 → on_unmount 决议 deny
        await pilot.pause()
        t.join(5)
        assert not t.is_alive()
        assert result["r"] == "deny"
        busy_task.cancel()
        app._busy_task = None
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_ctrl_q_stops_generation_not_exit(tmp_path, monkeypatch):
    """补漏扫描：Textual 默认 Ctrl+Q 直接退出绕过停止语义——覆盖为与 Ctrl+C
    同语义（生成中只停止）"""
    async def body(pilot, app, render, s, store):
        cancelled = {}
        started = threading.Event()

        async def slow_turn(line, ctx, rich_mode=True):
            started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled["yes"] = True
                raise
            return ""
        monkeypatch.setattr("agent.textual_ui.run_turn", slow_turn)
        app.query_one("#input").text = "长任务"
        await pilot.press("enter")
        for _ in range(200):
            if started.is_set():
                break
            await asyncio.sleep(0.01)
        assert app.busy is True
        await pilot.press("ctrl+q")
        await pilot.pause()
        assert cancelled.get("yes") is True
        assert not app._exit
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_esc_arm_disarmed_by_app_keys(tmp_path, monkeypatch):
    """补漏扫描：App 级按键（Ctrl+C 等）不经 DockInput.on_key——Esc 武装曾在
    停止后残留，下次 Enter 误插换行"""
    async def body(pilot, app, render, s, store):
        inp = app.query_one("#input")
        await pilot.press("escape")
        assert inp._esc_armed is True
        await pilot.press("ctrl+c")  # 空闲 → 停止语义分支（会 exit）
        await pilot.pause()
        assert inp._esc_armed is False  # App 级按键解除武装
        assert app._exit  # 空闲 Ctrl+C 仍退出（语义未变）
    _run_app_test(body, tmp_path, monkeypatch)


def test_app_empty_submit_not_in_history(tmp_path, monkeypatch):
    """补漏扫描：回车空输入曾写入空历史条目（污染 v3 ↑ 历史与 v4 Ctrl+R 列表）"""
    async def body(pilot, app, render, s, store):
        await pilot.press("enter")
        await pilot.pause()
        p = Path(str(tmp_path / "history.txt"))
        assert not p.exists() or p.read_text(encoding="utf-8").strip() == ""
    _run_app_test(body, tmp_path, monkeypatch)


# ==================== 回退链（run_repl 委托 v4，失败回退 v3） ====================


def test_run_repl_textual_failure_falls_back_to_v3(monkeypatch, tmp_path):
    """Textual 运行期失败（如无 VT 老控制台）→ run_repl 回退 v3 全屏 ptk 路径：
    重建 FullscreenRenderer（cwd/session 保留）+ 提示 + prompt_fn 正常消费"""
    import agent.terminal as terminal

    created = []

    class RecFSR(terminal.FullscreenRenderer):
        def __init__(self, **kw):
            super().__init__(**kw)
            created.append(self)

        def redraw(self):
            pass  # 测试环境不真清屏

        def enter_alt_screen(self):
            pass

        def exit_alt_screen(self):
            pass

    monkeypatch.setattr(terminal, "FullscreenRenderer", RecFSR)

    async def boom(*a, **kw):
        raise RuntimeError("Textual 驱动不可用")

    monkeypatch.setattr("agent.textual_ui.run_textual_repl", boom)

    store = TerminalSessionStore(path=str(tmp_path / "s.json"))
    s = store.new_session("claude")
    render = TextualRenderer(cwd="C:/work", session_id=s["id"])

    calls = []

    async def prompt():
        calls.append(1)
        return None

    asyncio.run(terminal.run_repl(s, store, prompt_fn=prompt, render=render))
    assert calls == [1]
    assert len(created) == 1
    assert created[0]._cwd == "C:/work"
    assert created[0]._session_id == s["id"]
    assert any(b["kind"] == "info" and "回退经典模式" in b["content"]
               for b in created[0]._blocks)


def test_run_repl_textual_happy_path(monkeypatch, tmp_path):
    """run_repl 收到 TextualRenderer → 委托 run_textual_repl（正常路径不碰
    ptk 代码）"""
    import agent.terminal as terminal

    captured = {}

    async def fake_textual_repl(session, store, render):
        captured["render"] = render
        captured["session"] = session

    monkeypatch.setattr("agent.textual_ui.run_textual_repl", fake_textual_repl)

    store = TerminalSessionStore(path=str(tmp_path / "s.json"))
    s = store.new_session("claude")
    render = TextualRenderer(cwd="C:/work", session_id=s["id"])

    async def prompt():
        raise AssertionError("v4 路径不应消费 prompt_fn")

    asyncio.run(terminal.run_repl(s, store, prompt_fn=prompt, render=render))
    assert captured["render"] is render
    assert captured["session"] is s
