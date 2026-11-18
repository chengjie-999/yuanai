# -*- coding: utf-8 -*-
"""重复消息事故修复测试（2026-11-18）：
① 连续相同工具结果去重（build_input_messages）
② 重复块检测（scripts/cleanup_dup_messages.find_dup_blocks）
③ (session_id, msg_id) 唯一索引兜底（0035 迁移）
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


# ---------- ① 连续相同工具结果去重 ----------

def _mk_sys():
    from langchain_core.messages import SystemMessage
    return SystemMessage(content="sys")


def test_consecutive_duplicate_tool_results_deduped():
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from yuanai_core.core.chat import build_input_messages

    history = [
        HumanMessage(content="查一下天气"),
        AIMessage(content="我来查", tool_calls=[]),
        ToolMessage(content="没有匹配", tool_call_id="t1"),
        ToolMessage(content="没有匹配", tool_call_id="t2"),
        ToolMessage(content="没有匹配", tool_call_id="t3"),
        ToolMessage(content="上海 18 度", tool_call_id="t4"),
        ToolMessage(content="上海 18 度", tool_call_id="t5"),
        AIMessage(content="查完了"),
    ]
    out = build_input_messages("继续", [], history, _mk_sys())
    tools = [m["content"] for m in out if m["role"] == "tool"]
    assert tools == ["没有匹配", "上海 18 度"]  # 连续相同各留一份


def test_non_consecutive_same_tool_results_kept():
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from yuanai_core.core.chat import build_input_messages

    history = [
        HumanMessage(content="a"),
        AIMessage(content="", tool_calls=[]),
        ToolMessage(content="结果X", tool_call_id="t1"),
        AIMessage(content="中间思考"),
        ToolMessage(content="结果X", tool_call_id="t2"),
    ]
    out = build_input_messages("继续", [], history, _mk_sys())
    tools = [m["content"] for m in out if m["role"] == "tool"]
    assert tools == ["结果X", "结果X"]  # 非连续不合并


# ---------- ② 重复块检测 ----------

def test_find_dup_blocks_detects_three_copies():
    from scripts.cleanup_dup_messages import find_dup_blocks
    base = [f"m{i}" for i in range(12)]
    seq = base + base + base + ["new1", "new2"]
    L, last_start, starts = find_dup_blocks(seq)
    assert L == 12
    assert last_start == 24  # 保留第三份副本 + 尾部新消息
    assert starts == [0, 12, 24]


def test_find_dup_blocks_no_dup_returns_none():
    from scripts.cleanup_dup_messages import find_dup_blocks
    seq = [f"m{i}" for i in range(20)]
    assert find_dup_blocks(seq) is None


def test_find_dup_blocks_legit_repeats_inside_block_ok():
    # 块内合法重复（如两次「继续」）不影响整块检测——重复单元取其最短周期
    from scripts.cleanup_dup_messages import find_dup_blocks
    base = ["a", "继续", "b", "继续", "c", "d", "e", "f"] * 2
    seq = base + base + base
    L, last_start, starts = find_dup_blocks(seq)
    assert L == 8          # 最短重复周期 = 单个 base
    assert last_start == 40  # 最后一个完整副本起点 = 40


def test_find_dup_blocks_variable_length_copies():
    # 真实事故形态：每份副本长度不一（39~48 条），步进比对会提前断走——
    # 位置比对必须找到最后一个完整副本起点
    from scripts.cleanup_dup_messages import find_dup_blocks
    base = [f"m{i}" for i in range(10)]
    seq = base + base + ["x1"] + base + ["x1", "x2"] + base + ["tail"]
    L, last_start, starts = find_dup_blocks(seq)
    assert L == 10
    assert starts == [0, 10, 21, 33]
    assert last_start == 33  # 最后一份完整副本起点


def test_cleanup_rescues_unique_stragglers():
    # 副本间隙里的唯一消息（真实事故中的藏文轮次）不在保留块中 → 救援保留
    from scripts.cleanup_dup_messages import find_dup_blocks
    base = [f"m{i}" for i in range(10)]
    straggler = "藏文问答"
    seq = base + base + [straggler] + base + ["tail"]
    L, last_start, _ = find_dup_blocks(seq)
    kept_sigs = set(seq[last_start:])
    del_sigs = [s for s in seq[:last_start] if s in kept_sigs]
    rescued = [s for s in seq[:last_start] if s not in kept_sigs]
    assert del_sigs == base * 2          # 两份旧副本全删
    assert rescued == [straggler]        # 唯一消息保留


# ---------- 时间换算/排序口径 ----------

def test_beijing_str_offset():
    from datetime import datetime, timedelta
    from yuanai_core.pure.beijing_time import beijing_str
    assert beijing_str(None) == ""
    dt = datetime(2026, 11, 18, 12, 30, 0)
    out = beijing_str(dt)
    assert out.startswith("2026-11-18")
    # 自校准：换算后的时间与原始时间的「时刻」差恰为北京与本机时钟的差——
    # 回推验证：beijing_str(dt) - dt 的偏移应为整 8 小时倍数（0 或 8h）
    parsed = datetime.strptime(out, "%Y-%m-%d %H:%M:%S")
    delta = parsed - dt
    assert delta.total_seconds() in (0, 8 * 3600)


# ---------- ③ 唯一索引兜底 ----------

@pytest.fixture(scope="module")
def db():
    try:
        from db.session import AgentDatabase
        return AgentDatabase()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


def test_unique_index_rejects_same_id(db):
    sid = f"uniq-{uuid.uuid4().hex[:12]}"
    mid = uuid.uuid4().hex
    try:
        with db.session() as s:
            s.execute(text(
                "INSERT INTO ai_chat (session_id, role, content, msg_id) "
                "VALUES (:s, 'user', 'hello', :m)"), {"s": sid, "m": mid})
            s.commit()
        with pytest.raises(IntegrityError):
            with db.session() as s:
                s.execute(text(
                    "INSERT INTO ai_chat (session_id, role, content, msg_id) "
                    "VALUES (:s, 'user', 'hello again', :m)"), {"s": sid, "m": mid})
                s.commit()
    finally:
        with db.session() as s:
            s.execute(text("DELETE FROM ai_chat WHERE session_id=:s"), {"s": sid})
            s.commit()
