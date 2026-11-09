# -*- coding: utf-8 -*-
"""P0 会话锁看门狗测试 — 锁超时强杀复位 / 停止联动 / 身份守卫清理

运行：pytest test/test_claude_bridge_watchdog.py -v（零网络：mock 子进程/任务）
"""
import asyncio
import os
import re
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # noqa: E402
sys.stdout.reconfigure(encoding='utf-8')

from agent import claude_bridge as cb  # noqa: E402
from yuanai_core.core.schemas import ChatRequest  # noqa: E402


def _req(sid="s1", rid="r1"):
    return ChatRequest(request_id=rid, session_id=sid, user_id=1,
                       messages=[{"role": "user", "content": "hi"}])


def _make_handler():
    return cb.ClaudeBridgeHandler(ws_send=None, server_url="", agent_id="1",
                                  agent_token="", sdk_mode=False)


async def _collect(agen):
    out = []
    async for ev in agen:
        out.append(ev)
    return out


# ---------------- 锁被占用：带已运行时长、未超时不复位 ----------------

def test_lock_busy_message_has_elapsed(monkeypatch):
    monkeypatch.setattr(cb, "LOCK_TIMEOUT", 600)

    async def main():
        h = _make_handler()
        key = "s1"
        lock = h._locks.setdefault(key, asyncio.Lock())
        await lock.acquire()
        h._lock_since[key] = time.monotonic() - 45
        out = await _collect(h.stream(_req()))
        assert len(out) == 1 and out[0].type == "error"
        m = re.search(r"(\d+)s", out[0].data)
        assert m and 40 <= int(m.group(1)) <= 49  # 提示带已运行时长
        assert key in h._locks  # 未超时：不复位锁
        lock.release()

    asyncio.run(main())


# ---------------- 看门狗：超时强杀子进程 + 复位锁 + 人话报错 ----------------

def test_lock_watchdog_kills_and_resets(monkeypatch):
    monkeypatch.setattr(cb, "LOCK_TIMEOUT", 60)

    async def main():
        h = _make_handler()
        key = "s1"
        lock = h._locks.setdefault(key, asyncio.Lock())
        await lock.acquire()
        h._lock_since[key] = time.monotonic() - 120  # 卡死 2 分钟
        state = {"killed": False}
        proc = SimpleNamespace(returncode=None, kill=lambda: state.update(killed=True))

        async def hung():
            await asyncio.sleep(60)

        task = asyncio.create_task(hung())
        h._active[key] = {"proc": proc, "task": task}

        out = await _collect(h.stream(_req(rid="r2")))
        await asyncio.sleep(0)             # 等取消送达
        assert len(out) == 1 and out[0].type == "error"
        assert "已终止" in out[0].data  # 人话报错
        assert state["killed"] is True     # 子进程被强杀
        assert task.cancelled()            # 活动任务被取消
        assert key not in h._locks         # 锁已复位（下个请求新建锁）
        lock.release()                     # 旧持有者退出，解锁废弃锁对象无副作用

    asyncio.run(main())


# ---------------- 停止联动：stop_request 杀挂起委派 ----------------

def test_stop_request_kills_active():
    async def main():
        h = _make_handler()
        key = "s1"
        state = {"killed": False}
        proc = SimpleNamespace(returncode=None, kill=lambda: state.update(killed=True))

        async def hung():
            await asyncio.sleep(60)

        task = asyncio.create_task(hung())
        h._active[key] = {"proc": proc, "task": task}
        h._rid_key["r1"] = key
        h._lock_since[key] = time.monotonic()
        lock = h._locks.setdefault(key, asyncio.Lock())
        await lock.acquire()

        h.stop("r1")
        await asyncio.sleep(0)             # 等取消送达
        assert state["killed"] is True
        assert task.cancelled()
        assert key not in h._locks
        assert h._rid_key == {} and h._lock_since == {}
        lock.release()

    asyncio.run(main())


def test_stop_unknown_rid_noop():
    async def main():
        h = _make_handler()
        h.stop("nope")  # 无对应活动任务：仅日志，不抛异常
        h.stop("")
    asyncio.run(main())


# ---------------- 身份守卫：旧持有者收尾不得误删新持有者簿记 ----------------

def test_stale_holder_cleanup_identity_guard(monkeypatch):
    monkeypatch.setattr(cb, "LOCK_TIMEOUT", 600)

    async def main():
        h = _make_handler()
        entered = asyncio.Event()

        async def fake_run(self, req, rid, prompt, lock_key=""):
            entered.set()
            await asyncio.sleep(3600)  # 模拟卡死
            yield {"type": "done", "data": "ok", "request_id": rid}

        monkeypatch.setattr(cb.ClaudeBridgeHandler, "_run_query", fake_run)
        key = "s1"

        # A 拿锁后卡死
        task_a = asyncio.create_task(_collect(h.stream(_req(rid="ra"))))
        await entered.wait()
        assert h._locks[key].locked()

        # B 触发看门狗：杀 A（取消任务）+ 复位锁
        monkeypatch.setattr(cb, "LOCK_TIMEOUT", -1)
        out_b = await _collect(h.stream(_req(rid="rb")))
        assert out_b and "已终止" in out_b[0].data

        # C 抢先登记新簿记（A 的取消收尾尚未送达）
        monkeypatch.setattr(cb, "LOCK_TIMEOUT", 600)
        entered.clear()
        task_c = asyncio.create_task(_collect(h.stream(_req(rid="rc"))))
        await entered.wait()
        active_c = h._active.get(key)
        assert active_c is not None and active_c["task"] is task_c

        # A 收尾：身份守卫保证不动 C 的簿记/锁
        task_a.cancel()
        await asyncio.sleep(0.05)
        assert task_a.done()
        assert h._active.get(key) is active_c
        assert key in h._locks and h._locks[key].locked()

        # C 正常收尾：簿记清干净
        task_c.cancel()
        await asyncio.sleep(0.05)
        assert task_c.done()
        assert h._active.get(key) is None
        assert h._rid_key == {} and h._lock_since == {}

    asyncio.run(main())
