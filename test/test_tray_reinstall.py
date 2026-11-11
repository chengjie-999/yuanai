# -*- coding: utf-8 -*-
"""T3 注销/停用兜底测试（2026-11-09）——凭据被拒停止盲重连 + 重新注册引导（零网络）

运行：pytest test/test_tray_reinstall.py -v
"""
import asyncio
import os
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # noqa: E402
sys.stdout.reconfigure(encoding='utf-8')

from agent import tray  # noqa: E402
from agent import ws_client as wsc  # noqa: E402
from agent.ws_client import AgentWSClient  # noqa: E402


# ---------------- WS 凭据被拒（T3 核心） ----------------

def test_ws_auth_rejected_stops_reconnect(monkeypatch):
    from websockets.exceptions import InvalidStatus

    async def main():
        w = AgentWSClient(server_url="ws://localhost", agent_id="1",
                          agent_name="t", capabilities=[])
        events = []
        w.on_auth_rejected(lambda code: events.append(code))

        async def fake_connect(*a, **k):
            raise InvalidStatus(SimpleNamespace(status_code=403))

        monkeypatch.setattr(wsc, "connect", fake_connect)
        await w.connect()  # 不无限循环：被拒后直接返回
        assert events == ["403"]
        assert w._running is False  # 停止盲重连，等重新注册

    asyncio.run(main())


def test_ws_auth_401_same_as_403(monkeypatch):
    from websockets.exceptions import InvalidStatus

    async def main():
        w = AgentWSClient(server_url="ws://localhost", agent_id="1",
                          agent_name="t", capabilities=[])
        events = []
        w.on_auth_rejected(lambda code: events.append(code))

        async def fake_connect(*a, **k):
            raise InvalidStatus(SimpleNamespace(status_code=401))

        monkeypatch.setattr(wsc, "connect", fake_connect)
        await w.connect()
        assert events == ["401"]

    asyncio.run(main())


def test_ws_handshake_5xx_not_auth_rejected(monkeypatch):
    from websockets.exceptions import InvalidStatus

    async def main():
        w = AgentWSClient(server_url="ws://localhost", agent_id="1",
                          agent_name="t", capabilities=[])
        events = []
        w.on_auth_rejected(lambda code: events.append(code))

        async def fake_connect(*a, **k):
            w._running = False  # 只模拟一轮，防重连循环挂住测试
            raise InvalidStatus(SimpleNamespace(status_code=500))

        monkeypatch.setattr(wsc, "connect", fake_connect)
        await w.connect()
        assert events == []  # 5xx 服务端问题 → 通用重连，不触发注销兜底

    asyncio.run(main())


# ---------------- 输入框（独立进程，绕开回调线程 tkinter 坑） ----------------

def test_inputbox_ps_non_windows(monkeypatch):
    monkeypatch.setattr(tray.os, "name", "posix")
    assert tray._inputbox_ps("t", "p") == ""


def test_inputbox_ps_reads_result(monkeypatch, tmp_path):
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(tray.os, "name", "nt")

    def fake_run(cmd, **k):
        (tmp_path / f"yuanai_input_{os.getpid()}.txt").write_text("YUAN-123", encoding="utf-8")
        return SimpleNamespace()

    monkeypatch.setattr(tray.subprocess, "run", fake_run)
    assert tray._inputbox_ps("t", "p") == "YUAN-123"


def test_inputbox_ps_cancel_empty(monkeypatch, tmp_path):
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(tray.os, "name", "nt")
    monkeypatch.setattr(tray.subprocess, "run", lambda *a, **k: SimpleNamespace())
    assert tray._inputbox_ps("t", "p") == ""  # 用户取消（无结果文件）


# ---------------- 托盘兜底流程 ----------------

def test_auth_rejected_notify_once(monkeypatch):
    t = tray.AgentTray("ws://localhost", "1", "t")
    notes = []
    t._icon = SimpleNamespace(notify=lambda msg, title: notes.append(msg))
    monkeypatch.setattr(tray, "_inputbox_ps", lambda *a, **k: "")  # 取消路径

    t._on_auth_rejected("403")
    assert t._reinstall_prompted is True
    assert any("解除关联" in n for n in notes)  # 人话通知

    t._on_auth_rejected("403")  # 每次进程只提示一次
    assert len(notes) == 1
    time.sleep(0.3)  # 等 daemon 线程跑完（输入框空返回即退）


def test_reinstall_flow_success(monkeypatch):
    import agent.main as am
    t = tray.AgentTray("ws://localhost", "1", "t")
    notes = []
    t._icon = SimpleNamespace(notify=lambda msg, title: notes.append(msg))
    monkeypatch.setattr(tray, "_inputbox_ps", lambda *a, **k: "YUAN-TEST-CODE")
    installed = {}

    def fake_install(server_url, code):
        installed["code"] = code

    monkeypatch.setattr(am, "do_install", fake_install)
    monkeypatch.setattr(am, "load_identity",
                        lambda: {"agent_id": "99", "agent_secret": "s2"})
    restarted = []
    t._restart_loops = lambda: restarted.append(1)
    t._reinstall_prompted = True  # 之前已提示过

    t._reinstall_flow("测试")

    assert installed["code"] == "YUAN-TEST-CODE"
    assert t.agent_id == "99" and t.agent_token == "s2"  # 身份已换
    assert restarted == [1]  # 全循环重建（持旧 secret 的线程同换）
    assert t._reinstall_prompted is False  # 注册成功复位，未来可再提示
    assert any("注册成功" in n for n in notes)
