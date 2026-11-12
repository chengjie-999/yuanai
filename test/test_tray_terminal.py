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


def test_native_cc_open_spawns_claude(monkeypatch):
    """托盘「Claude Code 原生终端」：探测 claude CLI → 新控制台窗口直接跑官方 TUI"""
    import shutil as sh
    t = tray.AgentTray("ws://localhost", "1", "t")
    notes = []
    t._icon = SimpleNamespace(notify=lambda msg, title: notes.append(msg))
    monkeypatch.setattr(sh, "which", lambda name: "C:/npm/claude")
    spawned = []
    monkeypatch.setattr(tray.subprocess, "Popen", lambda *a, **k: spawned.append((a, k)))
    t._on_native_cc_open(None, None)
    assert spawned and spawned[0][0][0][0] == "C:/npm/claude"
    if tray.os.name == "nt":
        assert "creationflags" in spawned[0][1]


def test_native_cc_open_missing_cli(monkeypatch):
    import shutil as sh
    t = tray.AgentTray("ws://localhost", "1", "t")
    notes = []
    t._icon = SimpleNamespace(notify=lambda msg, title: notes.append(msg))
    monkeypatch.setattr(sh, "which", lambda name: None)
    spawned = []
    monkeypatch.setattr(tray.subprocess, "Popen", lambda *a, **k: spawned.append(1))
    t._on_native_cc_open(None, None)
    assert not spawned  # 未安装不 spawn，只提示
    assert notes and "npm" in notes[0]  # 给出安装指引


def test_terminal_action_cooldown_blocks_rapid_clicks(monkeypatch):
    """防连点（2026-11-12）：冷却期内重复点托盘图标只通知不重复开窗"""
    import time
    t = tray.AgentTray("ws://localhost", "1", "t")
    notes = []
    t._icon = SimpleNamespace(notify=lambda msg, title: notes.append(msg))
    monkeypatch.setattr(tray.sys, "frozen", True, raising=False)
    monkeypatch.setattr(tray.sys, "executable", "C:/x/小元AI Agent.exe", raising=False)
    spawned = []
    monkeypatch.setattr(tray.subprocess, "Popen", lambda *a, **k: spawned.append(a))
    monkeypatch.setattr(tray, "_TERMINAL_LAST_LAUNCH", time.time())  # 刚开过

    t._terminal_action()
    assert not spawned
    assert notes and "防连点" in notes[0]

    monkeypatch.setattr(tray, "_TERMINAL_LAST_LAUNCH", 0.0)  # 冷却过后正常开
    t._terminal_action()
    assert spawned and "--run-terminal" in spawned[0][0]


def test_enable_console_vt_sets_dark_shell(monkeypatch):
    """自建控制台暗色壳（2026-11-12 用户拍板）：SetConsoleTextAttribute 黑底
    亮灰字 0x07——不随系统 conhost 默认主题（可能是浅色）走"""
    calls = []

    class _K:
        def GetStdHandle(self, h):
            return 77

        def GetConsoleMode(self, h, ref):
            return True

        def SetConsoleMode(self, h, m):
            calls.append(("mode", m))

        def SetConsoleTextAttribute(self, h, attr):
            calls.append(("attr", attr))

    fake_ctypes = SimpleNamespace(
        windll=SimpleNamespace(kernel32=_K()),
        c_uint32=lambda: SimpleNamespace(value=0),
        byref=lambda x: x,
    )
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)
    monkeypatch.setattr(tray.os, "name", "nt")
    tray._enable_console_vt()
    assert ("attr", 0x07) in calls      # 暗色壳已设置
    assert any(c[0] == "mode" for c in calls)  # VT 处理同开
