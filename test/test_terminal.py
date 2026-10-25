# -*- coding: utf-8 -*-
"""P1 终端对话 CLI 测试 — 会话存储 / 管道模式 / REPL 命令 / 渲染与桌宠事件

运行：pytest test/test_terminal.py -v（零网络：run_sdk_loop 与 call_llm 均为 mock）
"""
import asyncio
from types import SimpleNamespace
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agent import terminal  # noqa: E402


# ---------------- 会话存储 ----------------

def test_store_roundtrip(tmp_path):
    p = tmp_path / "terminal_sessions.json"
    store = terminal.TerminalSessionStore(str(p))
    s = store.new_session("claude")
    store.append(s["id"], "user", "你好", "claude")
    store.append(s["id"], "assistant", "你好！", "claude")

    store2 = terminal.TerminalSessionStore(str(p))
    store2.load()
    assert store2.latest()["id"] == s["id"]
    assert store2.latest()["messages"][-1]["content"] == "你好！"
    assert store2.latest()["mode"] == "claude"


def test_store_clear(tmp_path):
    store = terminal.TerminalSessionStore(str(tmp_path / "s.json"))
    s = store.new_session("claude")
    store.append(s["id"], "user", "x", "claude")
    store.clear(s["id"])
    assert store.latest()["messages"] == []


def test_store_caps(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal, "MAX_SESSIONS", 3)
    monkeypatch.setattr(terminal, "MAX_STORED_MSGS", 5)
    store = terminal.TerminalSessionStore(str(tmp_path / "s.json"))
    for i in range(5):
        s = store.new_session("claude")
        for j in range(10):
            store.append(s["id"], "user", f"m{j}", "claude")
    assert len(store._data["sessions"]) == 3
    assert len(store.latest()["messages"]) == 5
    assert store.latest()["messages"][-1]["content"] == "m9"


def test_store_latest_missing_file(tmp_path):
    store = terminal.TerminalSessionStore(str(tmp_path / "nope.json"))
    store.load()
    assert store.latest() is None


# ---------------- /claude 模式渲染（mock SDK loop） ----------------

def _fake_sdk_events():
    async def _gen(*args, **kwargs):
        yield {"type": "token", "data": "你好"}
        yield {"type": "tool_start", "data": {"name": "bash"}}
        yield {"type": "tool_end", "data": {"name": "bash", "output": "(exit=0)\nok"}}
        yield {"type": "done", "data": {"display_content": "你好", "reasoning_content": ""}}
    return _gen


def test_run_claude_query_renders_and_returns(capsys, monkeypatch):
    import agent.claude_loop as cl
    monkeypatch.setattr(cl, "load_credentials", lambda: "sk-test")
    monkeypatch.setattr(cl, "run_sdk_loop", _fake_sdk_events())

    result = asyncio.run(terminal.run_claude_query([{"role": "user", "content": "hi"}]))
    out = capsys.readouterr().out
    assert result == "你好"
    assert "你好" in out
    assert "bash" in out
    assert "(exit=0)" in out


def test_run_claude_query_no_credentials(capsys, monkeypatch):
    import agent.claude_loop as cl
    monkeypatch.setattr(cl, "load_credentials", lambda: None)
    result = asyncio.run(terminal.run_claude_query([{"role": "user", "content": "hi"}]))
    assert result == ""
    assert "凭证" in capsys.readouterr().out


def test_run_claude_query_error_event(capsys, monkeypatch):
    import agent.claude_loop as cl

    async def _err(*args, **kwargs):
        yield {"type": "error", "data": "执行失败"}

    monkeypatch.setattr(cl, "load_credentials", lambda: "sk-test")
    monkeypatch.setattr(cl, "run_sdk_loop", _err)
    result = asyncio.run(terminal.run_claude_query([{"role": "user", "content": "hi"}]))
    assert result == ""
    assert "执行失败" in capsys.readouterr().out


# ---------------- /chat 模式（v2 流式：mock get_llm().astream） ----------------

class _FakeChatLLM:
    def __init__(self, chunks, boom=None):
        self._chunks = chunks
        self._boom = boom

    async def astream(self, messages):
        if self._boom:
            raise self._boom
        for c in self._chunks:
            yield SimpleNamespace(content=c)


def test_run_chat_query(capsys, monkeypatch):
    monkeypatch.setattr("yuanai_core.core.lc.get_llm",
                        lambda model, temperature=0.1: _FakeChatLLM(["本地", "回答"]))
    result = asyncio.run(terminal.run_chat_query([{"role": "user", "content": "hi"}]))
    assert result == "本地回答"
    assert "本地回答" in capsys.readouterr().out


def test_run_chat_query_failure(capsys, monkeypatch):
    monkeypatch.setattr("yuanai_core.core.lc.get_llm",
                        lambda *a, **k: _FakeChatLLM([], boom=RuntimeError("endpoint closed")))
    result = asyncio.run(terminal.run_chat_query([{"role": "user", "content": "hi"}]))
    assert result == ""
    assert "调用失败" in capsys.readouterr().out


# ---------------- 审批 Y/N ----------------

def test_approve_yn_yes_and_deny(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    assert terminal._approve_yn("d1", "bash", "git commit -m x") == "approve"
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert terminal._approve_yn("d1", "bash", "git commit -m x") == "deny"
    monkeypatch.setattr("builtins.input", lambda prompt="": "no")
    assert terminal._approve_yn("d1", "bash", "git commit -m x") == "deny"


# ---------------- 管道模式 ----------------

def test_run_pipe_single_shot(capsys, monkeypatch):
    async def _fake_run_query(mode, messages, on_approval=None, render=None):
        assert mode == "claude"
        assert messages[0]["content"] == "问题"
        print("回答", end="")

    monkeypatch.setattr(terminal, "run_query", _fake_run_query)
    asyncio.run(terminal.run_pipe("问题", "claude"))
    assert "回答" in capsys.readouterr().out


# ---------------- REPL 命令 ----------------

def test_repl_commands_and_mode_switch(tmp_path, capsys, monkeypatch):
    store = terminal.TerminalSessionStore(str(tmp_path / "s.json"))
    s = store.new_session("claude")

    lines = ["你好", "/chat", "本地问题", "/clear", "/badcmd", "/quit"]
    queue = iter(lines)

    async def _fake_input(prompt=""):
        return next(queue)

    async def _fake_run_query(mode, messages, on_approval=None, render=None):
        return "回答"

    monkeypatch.setattr(terminal, "_ainput", _fake_input)
    monkeypatch.setattr(terminal, "run_query", _fake_run_query)
    asyncio.run(terminal.run_repl(s, store))

    # /clear 在「你好」「本地问题」两轮后执行 → 消息清零
    assert s["messages"] == []
    # 未知命令被忽略，不产生消息
    out = capsys.readouterr().out
    assert "未知命令" in out
    assert "已切换本地 LLM" in out


# ---------------- 桌宠事件联动 ----------------

def test_pet_events_on_query(capsys, monkeypatch):
    states = []

    def _fake_emit(state=None, tool=None, event=None):
        states.append((state, tool))

    monkeypatch.setattr("agent.pet_events.emit", _fake_emit)
    import agent.claude_loop as cl
    monkeypatch.setattr(cl, "load_credentials", lambda: "sk-test")
    monkeypatch.setattr(cl, "run_sdk_loop", _fake_sdk_events())

    asyncio.run(terminal.run_claude_query([{"role": "user", "content": "hi"}]))
    assert ("thinking", None) in states
    assert ("working", "bash") in states
    assert states[-1] == ("idle", None)


def test_pet_error_on_failure(monkeypatch):
    states = []

    def _fake_emit(state=None, tool=None, event=None):
        states.append((state, tool))

    monkeypatch.setattr("agent.pet_events.emit", _fake_emit)
    import agent.claude_loop as cl

    async def _err(*args, **kwargs):
        yield {"type": "error", "data": "boom"}

    monkeypatch.setattr(cl, "load_credentials", lambda: "sk-test")
    monkeypatch.setattr(cl, "run_sdk_loop", _err)
    asyncio.run(terminal.run_claude_query([{"role": "user", "content": "hi"}]))
    assert ("error", None) in states


# ---------------- 编码防护（Windows 管道 GBK/UTF-8 错位 + 网关脏字节） ----------------

def test_clean_text_strips_surrogates():
    dirty = "你好" + chr(0xdc80) + "世界"
    cleaned = terminal._clean_text(dirty)
    assert chr(0xdc80) not in cleaned
    assert "你好" in cleaned and "世界" in cleaned


def _fake_stdin(data: bytes):
    class _Buf:
        def read(self):
            return data

    return SimpleNamespace(buffer=_Buf())


def test_read_stdin_query_utf8(monkeypatch):
    monkeypatch.setattr(terminal.sys, "stdin", _fake_stdin("1+1等于几？".encode("utf-8")))
    assert terminal.read_stdin_query() == "1+1等于几？"


def test_read_stdin_query_gbk_fallback(monkeypatch):
    monkeypatch.setattr(terminal.sys, "stdin", _fake_stdin("你好世界".encode("gbk")))
    assert terminal.read_stdin_query() == "你好世界"


def test_read_stdin_query_invalid_bytes(monkeypatch):
    monkeypatch.setattr(terminal.sys, "stdin", _fake_stdin(b"\xff\xfe\x80abc"))
    q = terminal.read_stdin_query()
    assert "abc" in q
    assert chr(0xdc80) not in q


# ---------------- 托盘入口探测（三本地合一） ----------------

def test_find_launcher_dev_mode(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    launcher = terminal.find_terminal_launcher()
    assert launcher is not None
    python_exe, root = launcher
    assert os.path.isfile(os.path.join(root, "agent", "terminal.py"))
    assert python_exe == sys.executable


def test_find_launcher_frozen_probe(tmp_path, monkeypatch):
    # 模拟 dist\exe 布局：tmp/dist/app.exe，tmp 下含 venv + agent/terminal.py
    (tmp_path / "venv" / "Scripts").mkdir(parents=True)
    (tmp_path / "venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "terminal.py").write_text("#", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "dist" / "app.exe"))
    launcher = terminal.find_terminal_launcher()
    assert launcher is not None
    assert launcher[0].endswith(os.path.join("venv", "Scripts", "python.exe"))
    assert launcher[1] == str(tmp_path)


def test_find_launcher_frozen_none(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "app.exe"))
    assert terminal.find_terminal_launcher() is None
