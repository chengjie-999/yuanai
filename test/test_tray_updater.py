# -*- coding: utf-8 -*-
"""P0 更新器自愈测试 — %TEMP%\_MEI* 残留清理（零网络，临时目录隔离）

运行：pytest test/test_tray_updater.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # noqa: E402
sys.stdout.reconfigure(encoding='utf-8')

from agent import tray  # noqa: E402


@pytest.fixture
def fake_temp(tmp_path, monkeypatch):
    """把 TEMP/TMP 指到隔离目录，避免测试误删真实 _MEI 目录"""
    monkeypatch.setenv("TEMP", str(tmp_path))
    monkeypatch.setenv("TMP", str(tmp_path))
    return tmp_path


def test_cleanup_removes_stale_mei(fake_temp, monkeypatch):
    stale = fake_temp / "_MEI12345"
    stale.mkdir()
    (stale / "x.dll").write_bytes(b"old")
    not_mei = fake_temp / "_MET_not_mei"  # 前缀不匹配不动
    not_mei.mkdir()
    monkeypatch.setattr(tray, "_pid_alive", lambda pid: False)  # 12345 已死

    tray._cleanup_mei_residue()

    assert not stale.exists()          # 残留解包目录被清
    assert not_mei.exists()            # 非 _MEI 前缀不动


def test_cleanup_keeps_live_process_mei(fake_temp, monkeypatch):
    """目录名 _MEI{pid} 对应进程存活 → 跳过（2026-11-12 事故回归：
    误删在用解包目录 → 残缺目录被下次启动复用 → _tcl_data 缺失启动即崩）"""
    live = fake_temp / "_MEI99999"
    live.mkdir()
    (live / "_tcl_data").mkdir()
    monkeypatch.setattr(tray, "_pid_alive", lambda pid: pid == 99999)

    tray._cleanup_mei_residue()

    assert live.exists()
    assert (live / "_tcl_data").exists()


def test_cleanup_keeps_current_meipass(fake_temp, monkeypatch):
    current = fake_temp / "_MEIcurrent"
    current.mkdir()
    monkeypatch.setattr(sys, "_MEIPASS", str(current), raising=False)

    tray._cleanup_mei_residue()

    assert current.exists()            # 当前进程自己的解包目录不能删


def test_cleanup_silent_on_error(fake_temp, monkeypatch):
    """清理过程任何异常都被吞掉（不拖垮启动）"""
    monkeypatch.setattr(tray.logger, "info", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    (fake_temp / "_MEIx").mkdir()
    tray._cleanup_mei_residue()  # 不抛异常


# ---- #41 终端窗口一体化（2026-11-14）：管道感知 + WT 承载 ----

class _FakeStream:
    """可配置 fileno 的假 stdio 流"""

    def __init__(self, fileno_result):
        self._fileno = fileno_result
        self.reconfigure = lambda *a, **k: None

    def fileno(self):
        if isinstance(self._fileno, Exception):
            raise self._fileno
        return self._fileno


def test_stdio_attached_detects_valid_host(monkeypatch):
    """stdio 有效（WT/集成终端管道）→ True；无效/None → False"""
    monkeypatch.setattr(tray.sys, "stdout", _FakeStream(1))
    monkeypatch.setattr(tray.sys, "stderr", _FakeStream(2))
    assert tray._stdio_attached() is True

    monkeypatch.setattr(tray.sys, "stdout", None)
    monkeypatch.setattr(tray.sys, "stderr", None)
    assert tray._stdio_attached() is False

    monkeypatch.setattr(tray.sys, "stdout", _FakeStream(ValueError("closed")))
    monkeypatch.setattr(tray.sys, "stderr", None)
    assert tray._stdio_attached() is False


def test_run_terminal_skips_alloc_console_when_attached(monkeypatch):
    """stdio 已有宿主 → 不弹自建控制台；无宿主 → 兜底自建"""
    import agent.terminal as terminal_mod

    async def _fake_main():
        return None
    monkeypatch.setattr(terminal_mod, "main", _fake_main)

    called = []
    monkeypatch.setattr(tray, "_alloc_console", lambda: called.append(1))
    monkeypatch.setattr(tray, "_stdio_attached", lambda: True)
    tray._run_terminal_mode()
    assert called == []

    monkeypatch.setattr(tray, "_stdio_attached", lambda: False)
    tray._run_terminal_mode()
    assert called == [1]
