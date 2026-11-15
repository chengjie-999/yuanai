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
    """stdio 有效（WT/集成终端管道）→ True；无效/None → False
    （2026-11-15 加固：宿主句柄检测经 _get_std_handle——本测试固定为无句柄，
    验证 Python 层兜底逻辑）"""
    monkeypatch.setattr(tray, "_get_std_handle", lambda kind: 0)
    monkeypatch.setattr(tray.sys, "stdout", _FakeStream(1))
    monkeypatch.setattr(tray.sys, "stderr", _FakeStream(2))
    assert tray._stdio_attached() is True

    monkeypatch.setattr(tray.sys, "stdout", None)
    monkeypatch.setattr(tray.sys, "stderr", None)
    assert tray._stdio_attached() is False

    monkeypatch.setattr(tray.sys, "stdout", _FakeStream(ValueError("closed")))
    monkeypatch.setattr(tray.sys, "stderr", None)
    assert tray._stdio_attached() is False


def test_stdio_attached_detects_host_handle_with_none_python(monkeypatch):
    """#41 加固核心：windowed 引导器置空 sys.stdout 但 WT/IDE 继承的 STD
    句柄有效 → True（内嵌标签页而非误判无宿主去 AllocConsole）"""
    monkeypatch.setattr(tray.sys, "stdout", None)
    monkeypatch.setattr(tray.sys, "stderr", None)
    monkeypatch.setattr(tray, "_get_std_handle", lambda kind: 42 if kind == -11 else 7)
    assert tray._stdio_attached() is True


def test_attach_host_stdio_rebinds_when_python_none(monkeypatch):
    """#41 加固：宿主管道挂回 Python 层（含 sys.__stdout__——Textual
    WindowsDriver 依赖）；stdio 已可用则幂等跳过"""
    monkeypatch.setattr(tray, "_get_std_handle", lambda kind: 42 if kind != -10 else 7)
    opened = []

    class _FakeMsvcrt:
        @staticmethod
        def open_osfhandle(h, flags):
            opened.append((h, flags))
            return 100 + len(opened)
    monkeypatch.setattr(tray.sys, "stdout", None)
    monkeypatch.setattr(tray.sys, "stderr", None)
    monkeypatch.setattr(tray.sys, "stdin", None)
    monkeypatch.setattr(tray.sys, "__stdout__", None)

    fake_fd = []
    class _FakeFile:
        def __init__(self, fd, mode, **kw):
            self.fd = fd
            fake_fd.append(self)
        def fileno(self):
            return self.fd
    monkeypatch.setattr(tray.os, "fdopen", _FakeFile)
    import msvcrt as real_msvcrt
    monkeypatch.setattr(real_msvcrt, "open_osfhandle", _FakeMsvcrt.open_osfhandle)

    tray._attach_host_stdio()
    assert tray.sys.stdout is not None
    assert tray.sys.stdout.fileno() > 0
    assert tray.sys.__stdout__ is tray.sys.stdout  # Textual 依赖
    assert tray.sys.stdin is not None

    # 幂等：已可用时不再重挂
    before = tray.sys.stdout
    tray._attach_host_stdio()
    assert tray.sys.stdout is before


def test_attach_host_stdio_skips_when_ok(monkeypatch):
    """stdio 已可用 → 不重挂（幂等）"""
    monkeypatch.setattr(tray.sys, "stdout", _FakeStream(1))
    monkeypatch.setattr(tray.sys, "stderr", _FakeStream(2))
    calls = []
    monkeypatch.setattr(tray, "_get_std_handle", lambda kind: calls.append(kind) or 42)
    tray._attach_host_stdio()
    assert calls == []  # 未触碰句柄


def test_run_terminal_skips_alloc_console_when_attached(monkeypatch):
    """stdio 已有宿主 → 不弹自建控制台；无宿主 → 兜底自建"""
    import agent.terminal as terminal_mod

    async def _fake_main():
        return None
    monkeypatch.setattr(terminal_mod, "main", _fake_main)

    called = []
    monkeypatch.setattr(tray, "_alloc_console", lambda: called.append(1))
    monkeypatch.setattr(tray, "_stdio_attached", lambda: True)
    monkeypatch.setattr(tray, "_attach_host_stdio", lambda: called.append(2))
    tray._run_terminal_mode()
    assert called == [2]  # 有宿主：挂回（幂等）不弹窗

    called.clear()
    monkeypatch.setattr(tray, "_stdio_attached", lambda: False)
    tray._run_terminal_mode()
    assert called == [1]  # 无宿主：自建控制台


def test_run_mcp_entry_before_mutex(monkeypatch):
    """--run-mcp 分支（T13 分发形态）：force 挂回 stdio + build_server().run()
    执行；不经单实例互斥体（CC 随时拉起的 MCP 子进程与托盘实例共存是常态）"""
    import agent.tray as tray

    ran = {}

    class FakeServer:
        def run(self):
            ran["run"] = True

    monkeypatch.setattr(tray, "_attach_host_stdio",
                        lambda force=False: ran.setdefault("force", force))
    import agent.mcp_server as mcp_mod
    monkeypatch.setattr(mcp_mod, "build_server", lambda: FakeServer())
    mutex_calls = []
    monkeypatch.setattr(tray, "_acquire_single_instance",
                        lambda *a, **k: mutex_calls.append(1) or (None, False))

    import sys
    monkeypatch.setattr(sys, "argv", ["tray.py", "--run-mcp"])
    try:
        tray.main()
    except SystemExit as e:
        assert e.code == 0
    assert ran.get("run") is True
    assert ran.get("force") is True  # 协议入口强制挂回宿主管道（devnull 顶替防）
    assert mutex_calls == []
