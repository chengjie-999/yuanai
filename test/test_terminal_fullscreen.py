# -*- coding: utf-8 -*-
"""终端 TUI v3.0 全屏渲染测试（2026-11-12 #36）——零网络零终端：
Console(record=True, force_terminal=True) 注入，断言块状态与渲染文本。"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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
