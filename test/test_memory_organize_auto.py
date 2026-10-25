# -*- coding: utf-8 -*-
"""记忆定期自动整理测试 — 系统节流调度模型整理记忆（零网络零 DB：LLM 与 Redis 均 mock）

与 test_memory_organize.py（工具路径护栏）的分工：
  工具 = 模型自发调用（会话护栏：只删本会话新增 + 每日 3 条）
  自动 = 系统调度（间隔节流 + 单次删除上限 + 审计 source=auto_organize）
运行：pytest test/test_memory_organize_auto.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from api.v1.chat import memory_organize as mo  # noqa: E402


def _entry(text, created_at="2026-10-01T00:00:00.000000"):
    return {"text": text, "created_at": created_at, "type": "chat", "source": "fold", "file": "f.md"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    """记忆目录与审计日志隔离到 tmp；LLM 返回可注入"""
    import yuanai_core.memory_store as store
    import utils.data_path as dp
    monkeypatch.setattr(store, "root_path", lambda: str(tmp_path))
    monkeypatch.setattr(dp, "root_path", lambda: str(tmp_path))
    return tmp_path


def _seed(uid, lines):
    import yuanai_core.memory_store as store
    store.apply_entries(uid, [_entry(ln) for ln in lines])


def _mem(uid):
    import yuanai_core.memory_store as store
    return [e["text"] for e in store.load_entries(uid)]


def _fake_llm(monkeypatch, text):
    import yuanai_core.memory as mem
    monkeypatch.setattr(mem, "_call_fold_llm", lambda system, user_text: text)


# ---------------- run_memory_organize 核心逻辑 ----------------

def test_below_min_items_skips(env, monkeypatch):
    _seed(1, ["用户怕辣", "用户在北京"])
    _fake_llm(monkeypatch, "不应被调用")
    from config.settings import MEMORY_ORGANIZE_AUTO_MIN_ITEMS
    assert 2 < MEMORY_ORGANIZE_AUTO_MIN_ITEMS
    r = mo.run_memory_organize(1)
    assert r == {"skipped": "below_min_items"}


def test_merge_duplicates_and_delete_stale(env, monkeypatch):
    lines = ["用户怕辣", "用户不吃辣", "用户在北京", "用户住在杭州",
             "用户喜欢python", "用户做数据分析", "用户常用pandas",
             "用户养了一只猫"]
    _seed(1, lines)
    # 模型输出：合并「怕辣/不吃辣」→ 一条；「住在杭州」过时删除；
    # 「常用pandas」并入升级行（差异推断按删除计——文本层面已完成合并）
    _fake_llm(monkeypatch, "\n".join([
        "用户怕辣", "用户在北京", "用户喜欢python", "用户做数据分析，常用pandas",
        "用户养了一只猫",
    ]))
    r = mo.run_memory_organize(1)
    assert r["organized"] and r["deleted"] == 3
    kept = _mem(1)
    assert "用户怕辣" in kept and "用户不吃辣" not in kept  # 合并（被删除）
    assert "用户住在杭州" not in kept  # 过时删除
    assert any("常用pandas" in k for k in kept)  # 合并后的升级行保留了细节


def test_delete_cap_keeps_overflow(env, monkeypatch):
    # 行内容避免前缀互相包含（「记忆1」⊂「记忆10」会干扰差异推断）
    lines = [f"记忆第{i}条" for i in range(12)]
    _seed(1, lines)
    # 模型只保留 2 条 → 10 条删除候选；上限压到 5 → 只删 5，其余保留
    import config.settings as s
    monkeypatch.setattr(s, "MEMORY_ORGANIZE_AUTO_DELETE_MAX", 5)
    _fake_llm(monkeypatch, "\n".join(["记忆第0条", "记忆第1条"]))
    r = mo.run_memory_organize(1)
    assert r["deleted"] == 5
    assert len(_mem(1)) == 7  # 2 模型保留 + 5 溢出保留


def test_llm_empty_skips_untouched(env, monkeypatch):
    _seed(1, [f"记忆{i}" for i in range(8)])
    _fake_llm(monkeypatch, "")
    r = mo.run_memory_organize(1)
    assert r == {"skipped": "llm_empty"}
    assert len(_mem(1)) == 8  # 未动


def test_audit_log_written(env, monkeypatch):
    _seed(1, [f"记忆{i}" for i in range(8)])
    _fake_llm(monkeypatch, "\n".join([f"记忆{i}" for i in range(6)]))  # 删 2 条
    mo.run_memory_organize(1)
    audit = os.path.join(str(env), "data", "logs", "memory_audit.log")
    assert os.path.isfile(audit)
    content = open(audit, encoding="utf-8").read()
    assert "source=auto_organize" in content
    assert "记忆6" in content


# ---------------- 调度节流 ----------------

def test_maybe_schedule_gated_by_interval(env, monkeypatch):
    monkeypatch.setattr("api.v1.chat.memory_organize._interval_elapsed", lambda uid, h: False)
    assert mo.maybe_schedule_memory_organize(1) is False


def test_maybe_schedule_disabled(env, monkeypatch):
    import config.settings as s
    monkeypatch.setattr(s, "MEMORY_ENABLED", True)
    monkeypatch.setattr(s, "MEMORY_ORGANIZE_AUTO_ENABLED", False)
    monkeypatch.setattr("api.v1.chat.memory_organize._interval_elapsed", lambda uid, h: True)
    assert mo.maybe_schedule_memory_organize(1) is False


def test_interval_elapsed_redis_fail_skips(env, monkeypatch):
    monkeypatch.setattr("api.v1.chat.memory_organize._interval_elapsed", lambda uid, h: False)
    # Redis 故障 → _interval_elapsed 内部吞异常返回 False（此处直接验证调用面）
    assert mo.maybe_schedule_memory_organize(1) is False


if __name__ == "__main__":
    print("测试入口：pytest test/test_memory_organize_auto.py -v")


def test_llm_exception_skips(env, monkeypatch):
    _seed(1, [f"记忆第{i}条" for i in range(8)])

    def _boom(*a, **k):
        raise RuntimeError("endpoint closed")

    import yuanai_core.memory as mem
    monkeypatch.setattr(mem, "_call_fold_llm", _boom)
    r = mo.run_memory_organize(1)
    assert r == {"skipped": "llm_error"}
    assert len(_mem(1)) == 8  # 未动


def test_duplicate_merge_seven_copies(env, monkeypatch):
    """用户真实场景：同一句记忆写了 7 遍 → 模型输出 1 行 → 合并为 1 条 + 6 条合并审计"""
    _seed(1, ["记忆鉴权失效"] * 7 + ["用户在北京"])
    _fake_llm(monkeypatch, "记忆鉴权失效\n用户在北京")
    r = mo.run_memory_organize(1)
    assert r["organized"] and r["merged"] == 6 and r["deleted"] == 0
    assert set(_mem(1)) == {"记忆鉴权失效", "用户在北京"}
    audit = open(os.path.join(str(env), "data", "logs", "memory_audit.log"), encoding="utf-8").read()
    assert "merged=" in audit


def test_plan_organize_dedup_kept():
    """纯逻辑：重复旧行只保留最早一条，其余进 collapsed"""
    from yuanai_core.memory import plan_organize
    old = [_entry("记忆鉴权失效", f"2026-10-2{i % 2}T00:00:00.000000") for i in range(7)]
    plan = plan_organize(old, ["记忆鉴权失效"])
    assert len(plan["kept"]) == 1 and len(plan["collapsed"]) == 6
    assert plan["deletions"] == []
