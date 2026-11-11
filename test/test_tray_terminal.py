# -*- coding: utf-8 -*-
"""发布版内置终端测试（2026-11-11）—— --no-agent 参数 / 自建控制台入口 / 托盘菜单 spawn（零网络）

运行：pytest test/test_tray_terminal.py -v
"""
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # noqa: E402
sys.stdout.reconfigure(encoding='utf-8')

from agent import tray  # noqa: E402
from agent import terminal as tm  # noqa: E402


def test_terminal_no_agent_flag(monkeypatch):
    """--no-agent：REPL 不拉起后台 Agent（托盘进程已持云端连接，防双连互踢）"""
    monkeypatch.setattr(sys, "argv", ["yuan", "--no-agent"])
    args = tm.parse_args()
    assert args.no_agent is True
    monkeypatch.setattr(sys, "argv", ["yuan"])
    assert tm.parse_args().no_agent is False


def test_run_terminal_mode_calls_terminal(monkeypatch):
    called = {}

    async def fake_main():
        called["ok"] = True

    monkeypatch.setattr(tm, "main", fake_main)
    monkeypatch.setattr(tray, "_alloc_console", lambda: None)
    assert tray._run_terminal_mode() == 0
    assert called.get("ok") is True


def test_terminal_action_frozen_spawns_self(monkeypatch):
    """冻结 exe：托盘「终端对话」= 拉起自身 --run-terminal --no-agent 子进程
    （不再提示「无源码环境」）"""
    t = tray.AgentTray("ws://localhost", "1", "t")
    t._icon = SimpleNamespace(notify=lambda *a, **k: None)
    monkeypatch.setattr(tray.sys, "frozen", True, raising=False)
    monkeypatch.setattr(tray.sys, "executable", "C:/x/小元AI Agent.exe", raising=False)
    spawned = []
    monkeypatch.setattr(tray.subprocess, "Popen", lambda *a, **k: spawned.append(a))
    t._terminal_action()
    assert spawned and spawned[0][0][0].endswith("小元AI Agent.exe")
    assert "--run-terminal" in spawned[0][0]
    assert "--no-agent" in spawned[0][0]


def test_alloc_console_non_windows_noop(monkeypatch):
    monkeypatch.setattr(tray.os, "name", "posix")
    tray._alloc_console()  # 非 Windows 无操作，不抛异常
