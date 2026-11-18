# -*- coding: utf-8 -*-
"""重复消息事故修复测试（2026-11-18）：
① 连续相同工具结果去重（build_input_messages）
② 重复块检测（scripts/cleanup_dup_messages.find_dup_blocks）
③ (session_id, msg_id) 唯一索引兜底（0035 迁移）
④ 模型输入末条 prompt 重复剥离（最新问题发两遍——分享会话实测）
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


# ---------- ④ 末条 prompt 重复剥离 ----------

def test_drop_trailing_prompt_dup_strips():
    from api.v1.chat.router import _drop_trailing_prompt_dup
    history = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "在的"},
        {"role": "user", "content": "再发一条"},
    ]
    assert _drop_trailing_prompt_dup(history, "再发一条") == history[:2]


def test_drop_trailing_prompt_dup_keeps_mismatch():
    # 末条 user 与 prompt 不同文 → 原样保留（防御：不误剥真实历史）
    from api.v1.chat.router import _drop_trailing_prompt_dup
    history = [{"role": "user", "content": "上一轮的问题"}]
    assert _drop_trailing_prompt_dup(history, "这一轮的问题") == history


def test_drop_trailing_prompt_dup_non_user_tail():
    # 末条是 assistant → 原样保留
    from api.v1.chat.router import _drop_trailing_prompt_dup
    history = [{"role": "assistant", "content": "回答"}]
    assert _drop_trailing_prompt_dup(history, "任意") == history


def test_drop_trailing_prompt_dup_empty():
    from api.v1.chat.router import _drop_trailing_prompt_dup
    assert _drop_trailing_prompt_dup([], "x") == []
    assert _drop_trailing_prompt_dup([{"role": "user", "content": "x"}], "") \
        == [{"role": "user", "content": "x"}]


def test_drop_trailing_prompt_dup_multimodal_content():
    # 图片消息 content 是 list——按 text 部分比对
    from api.v1.chat.router import _drop_trailing_prompt_dup
    history = [{"role": "user",
                "content": [{"type": "text", "text": "看图说话"},
                            {"type": "image_url", "image_url": {"url": "data:img"}}]}]
    assert _drop_trailing_prompt_dup(history, "看图说话") == []


def test_cloud_fallback_input_no_duplicate_last_question():
    # 端到端管道（前端 payload → /stream 云端回退构造）：
    # 模型收到的输入里最新问题只出现一次
    from api.v1.chat.router import (
        _fix_history_for_api, _langchain_from_items, _drop_trailing_prompt_dup)
    from yuanai_core.core.views import view_for
    history = [
        {"role": "user", "content": "先整一个对话，给我打个招呼就可以。"},
        {"role": "assistant", "content": "你好，我是小元AI……"},
        {"role": "user", "content": "你现在是不是只有一轮对话？"},
        {"role": "assistant", "content": "不是一轮……"},
        {"role": "user", "content": "是上一个发了两次吗？还是之前都发两次？"},
    ]
    prompt = "是上一个发了两次吗？还是之前都发两次？"
    fixed = _fix_history_for_api(_drop_trailing_prompt_dup(history, prompt))
    envs = [{"sender": m.get("sender"), "recipient": m.get("recipient"),
             "turn": m.get("turn"), "type": m.get("type")} for m in fixed]
    view = view_for("orchestrator", fixed, envelopes=envs)
    out = _langchain_from_items(view, prompt, None, "SYSTEM")
    texts = [m["content"] for m in out if m["role"] == "user"]
    assert texts.count(prompt) == 1          # 最新问题只发一遍
    assert texts == ["先整一个对话，给我打个招呼就可以。",
                     "你现在是不是只有一轮对话？", prompt]  # 顺序完整


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


def test_sig_ignores_meta_envelope():
    # 生产干跑零命中根因：副本正文一致但 META 信封（turn 等）不同——
    # _sig 必须按剥 META 后的正文比对
    from scripts.cleanup_dup_messages import _sig
    a = "\x00META\x00{\"s\":\"orchestrator\",\"tn\":2}\x00今天天气不错"
    b = "\x00META\x00{\"s\":\"orchestrator\",\"tn\":5}\x00今天天气不错"
    c = "今天天气不错"
    assert _sig("assistant", a, "") == _sig("assistant", b, "") == _sig("assistant", c, "")
    assert _sig("assistant", a, "") != _sig("assistant", "今天天气不错啊", "")


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
