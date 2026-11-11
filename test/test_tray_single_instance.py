# -*- coding: utf-8 -*-
"""单实例保护测试（2026-11-09 多开根治）——命名互斥体 / 第二实例提示（零真实互斥体）

运行：pytest test/test_tray_single_instance.py -v
"""
import ctypes
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # noqa: E402
sys.stdout.reconfigure(encoding='utf-8')

from agent import tray  # noqa: E402


class FakeKernel32:
    """GetLastError 按序列返回值；记录 create/close 次数"""

    def __init__(self, errors):
        self._errors = list(errors)
        self.created = 0
        self.closed = 0

    def CreateMutexW(self, *a):
        self.created += 1
        return 12345

    def GetLastError(self):
        return self._errors.pop(0) if self._errors else 0

    def CloseHandle(self, h):
        self.closed += 1


def _patch(monkeypatch, errors, capture_box=False):
    boxes = []
    fake = SimpleNamespace(
        kernel32=FakeKernel32(errors),
        user32=SimpleNamespace(MessageBoxW=lambda *a, **k: boxes.append(a)),
    )
    monkeypatch.setattr(ctypes, "windll", fake)
    return fake, boxes


def test_first_launch_acquires(monkeypatch):
    fake, _ = _patch(monkeypatch, [0])
    handle, dup = tray._acquire_single_instance(wait_s=0)
    assert dup is False and handle == 12345
    assert fake.kernel32.created == 1


def test_duplicate_launch_detected(monkeypatch):
    fake, _ = _patch(monkeypatch, [183, 183])  # 等待窗口内始终占用
    handle, dup = tray._acquire_single_instance(wait_s=0.05)
    assert dup is True and handle is None
    assert fake.kernel32.closed >= 1  # 等待期间释放检查句柄


def test_handover_window_reacquires(monkeypatch):
    fake, _ = _patch(monkeypatch, [183, 0])  # 旧实例退出 → 交接成功
    handle, dup = tray._acquire_single_instance(wait_s=0.3)
    assert dup is False and handle == 12345
    assert fake.kernel32.closed >= 1


def test_non_windows_passthrough(monkeypatch):
    monkeypatch.setattr(tray.os, "name", "posix")
    handle, dup = tray._acquire_single_instance(wait_s=0)
    assert (handle, dup) == (None, False)


def test_api_failure_silent(monkeypatch):
    def boom(*a, **k):
        raise OSError("no ctypes")
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(kernel32=SimpleNamespace(CreateMutexW=boom)))
    handle, dup = tray._acquire_single_instance(wait_s=0)
    assert (handle, dup) == (None, False)  # 保护失败放行，不崩启动


def test_duplicate_messagebox(monkeypatch):
    _, boxes = _patch(monkeypatch, [0])
    tray._notify_already_running()
    assert len(boxes) == 1
    args = boxes[0]
    assert "已经在运行" in str(args[1])  # 文案带「已在运行」指引
    assert "托盘图标" in str(args[1])
