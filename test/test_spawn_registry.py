# -*- coding: utf-8 -*-
"""P0 退出清子进程测试 — claude 子进程 PID 登记 / tree-kill（零真实进程）

运行：pytest test/test_spawn_registry.py -v
"""
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # noqa: E402
sys.stdout.reconfigure(encoding='utf-8')

from agent import bridge_policy as bp  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_registry():
    bp._SPAWNED_PIDS.clear()
    yield
    bp._SPAWNED_PIDS.clear()


def test_register_unregister():
    proc = SimpleNamespace(pid=1234)
    bp.register_spawned_proc(proc)
    assert 1234 in bp._SPAWNED_PIDS
    bp.unregister_spawned_proc(proc)
    assert 1234 not in bp._SPAWNED_PIDS
    bp.unregister_spawned_proc(SimpleNamespace(pid=5678))  # 未登记的幂等


def test_kill_spawned_tree_windows(monkeypatch):
    calls = []
    monkeypatch.setattr(bp.os, "name", "nt")
    monkeypatch.setattr(bp.subprocess, "run",
                        lambda *a, **k: calls.append((a, k)) or SimpleNamespace())
    bp.register_spawned_proc(SimpleNamespace(pid=111))
    bp.register_spawned_proc(SimpleNamespace(pid=222))

    n = bp.kill_spawned_tree()

    assert n == 2
    assert bp._SPAWNED_PIDS == set()  # 清杀清单已清空
    assert len(calls) == 2
    for (args, _kwargs) in calls:
        assert args[0][0] == "taskkill"
        assert "/T" in args[0] and "/F" in args[0]      # 整树强杀
    got_pids = {int(a[0][2]) for (a, _k) in calls}       # 集合迭代顺序不定，按集合比
    assert got_pids == {111, 222}


def test_kill_spawned_tree_silent_failure(monkeypatch):
    def boom(*a, **k):
        raise OSError("taskkill not found")
    monkeypatch.setattr(bp.os, "name", "nt")
    monkeypatch.setattr(bp.subprocess, "run", boom)
    bp.register_spawned_proc(SimpleNamespace(pid=999))

    assert bp.kill_spawned_tree() == 0  # 异常静默，不抛
    assert bp._SPAWNED_PIDS == set()


def test_register_silent():
    """登记异常（pid 缺失等）静默吞掉，不影响委派主流程"""
    bp.register_spawned_proc(SimpleNamespace())  # 无 pid 属性 → 静默
