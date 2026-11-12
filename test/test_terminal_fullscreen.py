# -*- coding: utf-8 -*-
"""终端 TUI v3.0 全屏渲染测试（2026-11-12 #36）——零网络零终端：
Console(record=True, force_terminal=True) 注入，断言块状态与渲染文本。"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from rich.console import Console  # noqa: E402

from agent import terminal  # noqa: E402


def _renderer(**kw):
    from rich.console import Console
    console = Console(record=True, force_terminal=True, width=100,
                      color_system="standard")
    return terminal.FullscreenRenderer(
        console=console, cwd="D:\\code\\yuanai", session_id="abcd1234ef",
        status_provider=lambda: "online", **kw)


def _out(r) -> str:
    """导出并清空录制缓冲（每次调用只取新增帧，Live 流式帧可先行排掉）"""
    return r._console.export_text(clear=True)


# ---------------- 块累积（流式接口） ----------------

def test_blocks_accumulate_fold_semantics():
    """思考挂工具卡上方（网页同款）：reasoning→tool 快照折叠块；首 token 余思考
    →最终思考；done→answer 块。thinking/tool 默认折叠、answer 展开。"""
    r = _renderer()
    r.reasoning("在想问题")
    r.tool_start("bash")
    r.tool_end("bash", "(exit=0)\nok")
    r.token("你好")
    r.reasoning("补充思考")
    r.done()
    kinds = [b["kind"] for b in r._blocks]
    assert kinds == ["thinking", "tool", "thinking", "answer"]
    assert r._blocks[0]["folded"] is True
    assert "思考" in r._blocks[0]["title"] and "1 次工具调用" in r._blocks[0]["title"]
    assert r._blocks[1]["folded"] is True and r._blocks[1]["title"] == "⚙ bash"
    assert r._blocks[2]["folded"] is True and "最终思考" in r._blocks[2]["title"]
    assert r._blocks[3]["folded"] is False
    assert r._blocks[3]["content"] == "你好"


def test_redraw_contains_header_and_blocks():
    """空闲重绘：状态栏（在线点/模式/工作目录/会话）+ 折叠块标题可见、
    折叠内容不可见；展开后内容可见（Enter 展开语义）"""
    r = _renderer()
    r.reasoning("秘密推理内容")
    r.tool_start("bash")
    r.tool_end("bash", "输出内容")
    r.done()
    _out(r)          # 排掉流式 Live 帧（含思考原文）与 done 内重绘帧
    r.redraw()       # 干净的空闲重绘帧
    out = _out(r)
    assert "在线" in out
    assert "claude" in out
    assert "yuanai" in out          # cwd 截断保留尾部
    assert "abcd1234" in out        # 会话号
    assert "⚙ bash" in out
    assert "思考" in out
    assert "秘密推理内容" not in out  # 折叠：内容不可见
    # 选中并展开思考块
    r.sel = 0
    r._blocks[0]["folded"] = False
    r.redraw()
    out2 = _out(r)
    assert "秘密推理内容" in out2
    assert "输出内容" not in out2    # 工具块仍折叠


def test_scroll_window_hides_tail():
    """PgUp 滚动：scroll_blocks>0 隐藏尾部最新块（回看历史）；PgDn 归零跟随"""
    r = _renderer()
    for i in range(6):
        r._blocks.append({"kind": "info", "title": "", "content": f"m{i}",
                          "folded": False})
    r.scroll_blocks = 2
    r.redraw()
    out = _out(r)
    assert "m5" not in out and "m4" not in out  # 最新两块被隐藏
    assert "m3" in out and "m0" in out
    r.scroll_blocks = 0
    r.redraw()
    assert "m5" in _out(r)


def test_info_error_interrupted_blocks():
    r = _renderer()
    r.info("提示行")
    r.error("失败原因")
    r.interrupted()
    kinds = [b["kind"] for b in r._blocks]
    assert kinds == ["info", "error", "info"]
    assert r._blocks[1]["content"] == "失败原因"
    assert "已停止生成" in r._blocks[2]["content"]


def test_pending_input_and_sel_clamp():
    """刷新哨兵机制：pending_input 保留未提交输入；sel 越界在重绘时归位"""
    r = _renderer()
    r.pending_input = "未提交的文字"
    r.sel = 99  # 越界
    r.redraw()
    assert r.pending_input == "未提交的文字"
    assert r.sel is None


# ---------------- run_repl 哨兵循环 ----------------

def test_run_repl_refresh_sentinel_redraws(capsys, monkeypatch, tmp_path):
    """prompt_fn 返回 _REFRESH → FullscreenRenderer.redraw 被调用且继续循环"""
    calls = []

    class _FakeFull(terminal.FullscreenRenderer):
        def __init__(self):
            from rich.console import Console
            super().__init__(console=Console(record=True, force_terminal=True),
                             cwd="x", session_id="s1")

        def redraw(self):
            calls.append(1)

    renderer = _FakeFull()
    seq = iter([terminal._REFRESH, terminal._REFRESH, None])

    async def _prompt():
        return next(seq)

    store = terminal.TerminalSessionStore(str(tmp_path / "t.json"))
    s = store.new_session("claude")
    asyncio.run(terminal.run_repl(s, store, prompt_fn=_prompt, render=renderer))
    assert len(calls) == 2  # 两次哨兵各触发一次重绘，第三次 None 退出


# ---------------- 托盘 WT 承载 ----------------

def test_open_windows_terminal_preferred(monkeypatch):
    import shutil as _shutil
    from agent import tray
    captured = {}

    class _P:
        def __init__(self, cmd, **kw):
            captured["cmd"] = cmd

    monkeypatch.setattr(_shutil, "which", lambda name: "C:\\wt.exe" if name in ("wt.exe", "wt") else None)
    monkeypatch.setattr(tray.subprocess, "Popen", _P)
    assert tray._open_in_windows_terminal(["py", "-m", "agent.terminal"],
                                          cwd="D:\\code") is True
    assert captured["cmd"][0] == "C:\\wt.exe"
    assert "new-tab" in captured["cmd"] and "D:\\code" in captured["cmd"]


def test_open_windows_terminal_fallback(monkeypatch):
    import shutil as _shutil
    from agent import tray
    monkeypatch.setattr(_shutil, "which", lambda name: None)
    assert tray._open_in_windows_terminal(["py"], cwd=".") is False


# ---------------- 网站对话入口（2026-11-12） ----------------

def test_web_chat_url_env_override(monkeypatch):
    monkeypatch.setenv("WEB_CHAT_URL", "https://example.com/chat")
    assert terminal.web_chat_url() == "https://example.com/chat"


def test_web_chat_url_local_dev(monkeypatch):
    """本地联调（身份文件 server_url=localhost）→ 前端 5173"""
    monkeypatch.delenv("WEB_CHAT_URL", raising=False)
    import agent.main as am
    monkeypatch.setattr(am, "load_identity", lambda: {"server_url": "ws://localhost:8000"})
    assert terminal.web_chat_url() == "http://localhost:5173/chat"


def test_web_chat_url_prod_default(monkeypatch):
    monkeypatch.delenv("WEB_CHAT_URL", raising=False)
    import agent.main as am
    monkeypatch.setattr(am, "load_identity", lambda: {"server_url": "wss://cjyuanai.cn"})
    assert terminal.web_chat_url() == "https://cjyuanai.cn/chat"


def test_run_repl_web_command_opens_browser(capsys, monkeypatch, tmp_path):
    """/web 命令 → 打开浏览器（后台线程，短轮询等待）+ 提示语含 URL"""
    import time
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))
    import agent.main as am
    monkeypatch.setattr(am, "load_identity", lambda: {"server_url": "wss://cjyuanai.cn"})
    store = terminal.TerminalSessionStore(str(tmp_path / "t.json"))
    s = store.new_session("claude")
    seq = iter(["/web", None])

    async def _prompt():
        return next(seq)

    asyncio.run(terminal.run_repl(s, store, prompt_fn=_prompt))
    out = capsys.readouterr().out
    assert "正在打开网站对话" in out
    for _ in range(50):  # daemon 线程短暂等待（不能全局 mock Thread——tqdm 等子类会崩）
        if opened:
            break
        time.sleep(0.02)
    assert opened == ["https://cjyuanai.cn/chat"]


def test_status_bar_has_web_entry():
    """状态栏含「F2 网站对话」入口（全屏渲染器 header）。
    分开断言：其它测试残留的桌宠状态会让状态栏变长换行（F2 与 网站对话 分列两行）"""
    r = _renderer()
    r.redraw()
    out = _out(r)
    assert "F2" in out
    assert "网站对话" in out


# ---------------- v3.2 #38 观测右栏 / 计划视图 / 桌宠色点 ----------------

def _observe(**kw):
    return {"online": True, "age_s": 30, "latest": {"message": "工具调用: bash"},
            "activities": [{"message": "工具调用: bash", "ts": kw.pop("ts", None)}],
            **kw}


def test_observe_panel_side_by_side():
    """观测右栏：云端通道可用 + 宽终端 → 与块流并排；状态点/最近活动/
    token 消耗可见，对话块不受影响"""
    import time as _t
    r = _renderer()
    r._observe_ready = True
    r._blocks.append({"kind": "info", "title": "", "content": "欢迎", "folded": False})
    r.set_usage(1234, 500)
    r.tick_observation(_observe(ts=_t.time() - 30))
    _out(r)          # tick 触发的 redraw 排掉
    r.redraw()
    out = _out(r)
    assert "执行观测" in out
    assert "活跃" in out and "30s" in out
    assert "工具调用: bash" in out
    assert "1234 tokens" in out and "缓存 500" in out
    assert "欢迎" in out  # 对话块仍在（左列）


def test_observe_panel_hidden_without_client_or_narrow():
    """无云端通道（无身份）或窄终端 → 右栏不渲染（降级不报错）"""
    r = _renderer()
    r._blocks.append({"kind": "info", "title": "", "content": "m0", "folded": False})
    r._observe_ready = False
    r.redraw()
    assert "执行观测" not in _out(r)
    r2 = _renderer()
    r2._observe_ready = True
    r2._console._width = 60  # 窄终端（<72）：右栏让位
    r2.redraw()
    assert "执行观测" not in _out(r2)


def test_observe_panel_states_offline_stale_error():
    import time as _t
    r = _renderer()
    r._observe_ready = True
    r.tick_observation({"online": False, "latest": None, "activities": []})
    _out(r); r.redraw()
    assert "○ 离线" in _out(r)
    r.tick_observation({"online": True, "age_s": 400, "latest": {"message": "x"},
                        "activities": [{"message": "x", "ts": _t.time() - 400}]})
    _out(r); r.redraw()
    out = _out(r)
    assert "无活动" in out and "可能已无响应" in out
    r.tick_observation({"error": True})
    _out(r); r.redraw()
    out = _out(r)
    assert "云端不可用" in out and "设备绑定" in out


def test_tick_observation_repaint_guards():
    """轮询注入的渲染时机守卫：ptk 输入等待中只更新状态不重绘（防与输入行
    打架）；Live 流式中走帧更新；非输入态整屏 redraw"""
    calls = []

    class _Spy(terminal.FullscreenRenderer):
        def redraw(self):
            calls.append("redraw")

    r = _Spy(console=Console(record=True, force_terminal=True, width=100),
             cwd="x", session_id="s1")
    r._prompt_active = True
    r.tick_observation(_observe())
    assert calls == []          # 输入等待中：不重绘，只更新状态
    assert r._observe["age_s"] == 30
    r._prompt_active = False
    r.tick_observation(_observe())
    assert calls == ["redraw"]  # 非输入态：整屏重绘
    calls.clear()
    r.reasoning("思考中")       # 起 Live（流式）
    r.tick_observation(_observe())
    assert calls == []          # 流式中：走 Live 帧更新，不整屏重绘


def test_plan_view_list_and_detail():
    """计划队列全屏视图：列表（状态词+进度条+步数）→ 详情（步骤逐行）→
    set_plan_view(None) 回到对话流块"""
    r = _renderer()
    r._blocks.append({"kind": "info", "title": "", "content": "m0", "folded": False})
    r.show_plans([
        {"id": 1, "title": "销售数据 RFM 分析", "status": "running", "progress": 57,
         "done_steps": 3, "total_steps": 5, "message": "正在执行"},
        {"id": 2, "title": "竞品页面采集", "status": "queued", "progress": 0,
         "done_steps": 0, "total_steps": 2, "message": ""},
    ])
    r.redraw()
    out = _out(r)
    assert "计划队列" in out
    assert "销售数据 RFM 分析" in out and "执行中" in out
    assert "57%" in out and "3/5 步" in out
    assert "竞品页面采集" in out and "排队中" in out
    assert "m0" not in out          # 计划视图替换对话流
    r.show_plans([], {"title": "销售数据 RFM 分析", "status": "running",
                      "progress": 57, "done_steps": 3, "total_steps": 5,
                      "steps": [
                          {"step_no": 1, "skill": "analysis", "desc": "数据清洗",
                           "status": "done", "progress": 100},
                          {"step_no": 2, "skill": "analysis", "desc": "RFM 分群",
                           "status": "running", "progress": 60},
                          {"step_no": 3, "skill": "analysis", "desc": "出报告",
                           "status": "failed", "progress": 0, "error": "脚本报错"},
                      ]})
    r.redraw()
    out = _out(r)
    assert "数据清洗" in out and "RFM 分群" in out and "出报告" in out
    assert "60%" in out and "脚本报错" in out
    r.set_plan_view(None)
    r.redraw()
    assert "m0" in _out(r)          # 退出计划视图 → 对话流块恢复


def test_plan_view_empty_hint():
    r = _renderer()
    r.show_plans([])
    r.redraw()
    out = _out(r)
    assert "暂无计划" in out


def test_pet_state_dot_in_header(monkeypatch):
    """桌宠六态色点进状态栏：working/sleeping 的点形态不同（●/○），词保真"""
    import agent.pet_events as pe
    monkeypatch.setattr(pe, "last_state", lambda: "working")
    r = _renderer()
    r.redraw()
    out = _out(r)
    assert "● 宠:working" in out
    monkeypatch.setattr(pe, "last_state", lambda: "sleeping")
    r.redraw()
    out = _out(r)
    assert "○ 宠:sleeping" in out


def test_header_no_markup_literals():
    """#38 顺手修复：Text.assemble 不解析 markup——状态栏曾显示字面
    [green]● 在线[/green]（v3.0 遗留）；现在应为纯文本 + ANSI 样式"""
    import io
    from rich.console import Console
    buf = io.StringIO()
    r = terminal.FullscreenRenderer(
        console=Console(file=buf, force_terminal=True, width=100,
                        color_system="standard"),
        cwd="x", session_id="s1", status_provider=lambda: "online")
    r.redraw()
    s = buf.getvalue()
    assert "[green]" not in s and "[bold]" not in s
    assert "\x1b[" in s          # 样式以 ANSI 生效
    assert "● 在线" in s


def test_run_repl_plan_command_views(capsys, monkeypatch, tmp_path):
    """/plan → 计划队列视图（fullscreen renderer）；/plan 1 → 详情；无云端
    客户端时人话报错不崩"""
    class _FakeClient:
        def list_plans(self):
            return [{"id": 7, "title": "RFM 分析", "status": "queued",
                     "progress": 0, "done_steps": 0, "total_steps": 3, "message": ""}]

        def plan_detail(self, pid):
            return {"title": "RFM 分析", "status": "queued", "progress": 0,
                    "done_steps": 0, "total_steps": 3,
                    "steps": [{"step_no": 1, "skill": "analysis", "desc": "数据清洗",
                               "status": "pending", "progress": 0}]}

    monkeypatch.setattr(terminal, "_make_cloud_client", lambda: _FakeClient())
    store = terminal.TerminalSessionStore(str(tmp_path / "t.json"))
    s = store.new_session("claude")
    seq = iter(["/plan", "/plan 1", "/quit"])
    from rich.console import Console
    render = terminal.FullscreenRenderer(
        console=Console(record=True, force_terminal=True, width=100), cwd="x",
        session_id="s1")
    import asyncio

    async def _prompt():
        return next(seq)

    asyncio.run(terminal.run_repl(s, store, prompt_fn=_prompt, render=render))
    out = render._console.export_text()
    assert "计划队列" in out and "RFM 分析" in out       # 列表视图
    assert "数据清洗" in out                              # 详情视图


def test_run_repl_plan_no_identity(capsys, monkeypatch, tmp_path):
    """无本机 Agent 身份：/plan 人话提示，不崩"""
    monkeypatch.setattr(terminal, "_make_cloud_client", lambda: None)
    store = terminal.TerminalSessionStore(str(tmp_path / "t.json"))
    s = store.new_session("claude")
    seq = iter(["/plan", None])
    import asyncio

    async def _prompt():
        return next(seq)

    asyncio.run(terminal.run_repl(s, store, prompt_fn=_prompt))
    out = capsys.readouterr().out
    assert "绑定设备" in out
