# -*- coding: utf-8 -*-
"""记忆折叠纯函数测试 — 零 DB 零 LLM 零花费

运行：pytest test/test_memory_pure.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from yuanai_core.memory import (  # noqa: E402
    strip_meta, build_transcript, parse_facts, merge_facts, should_fold,
)


# ---------------- strip_meta ----------------

def test_strip_meta():
    assert strip_meta("\x00META\x00{\"s\":\"analysis\"}\x00正文内容") == "正文内容"
    assert strip_meta("普通消息") == "普通消息"
    assert strip_meta("") == ""


# ---------------- build_transcript ----------------

def test_transcript_dislike_removed_and_tagged():
    msgs = [
        {"role": "user", "content": "我住在杭州"},
        {"role": "assistant", "content": "好的，记住了"},
        {"role": "assistant", "content": "独家秘闻：用户其实住在火星"},
    ]
    text, k = build_transcript(msgs, 0, 3, disliked={2})
    assert k == 3
    assert "独家秘闻" not in text
    assert "用户点踩" in text
    assert "我住在杭州" in text


def test_transcript_char_budget():
    # 两条 2000 字消息 + 3000 字预算：第一条放得下，第二条放不下 → k=1
    msgs = [{"role": "user", "content": "甲" * 2000},
            {"role": "user", "content": "乙" * 2000}]
    text, k = build_transcript(msgs, 0, 2, set(), max_chars=3000)
    assert k == 1
    assert "乙" not in text

    # 唯一一条超长消息：截断到 3000 且 k=1
    msgs2 = [{"role": "user", "content": "字" * 20000}]
    text2, k2 = build_transcript(msgs2, 0, 1, set(), max_chars=5000)
    assert k2 == 1
    assert len(text2) <= 3000 + 50


# ---------------- parse_facts ----------------

def test_parse_facts_strips_markup_and_dedups():
    raw = """```
- 用户是数据分析师
1、用户怕辣
* 用户是数据分析师
（2）喜欢 pandas

以下是要点：
说明：这些是事实
"""
    facts = parse_facts(raw)
    assert facts == ["用户是数据分析师", "用户怕辣", "喜欢 pandas"]


def test_parse_facts_empty_and_limits():
    assert parse_facts("") == []
    assert parse_facts("```\n```") == []
    many = [f"事实{i}" for i in range(30)]
    facts = parse_facts("\n".join(many), max_items=10)
    assert len(facts) == 10
    assert facts[0] == "事实0"


# ---------------- merge_facts ----------------

def test_merge_facts_dedup_and_limits():
    merged, added = merge_facts(["怕辣", "做跨境电商"], ["怕辣", "喜欢 pandas", "跨境电商"], 100, 2000)
    assert merged == ["怕辣", "做跨境电商", "喜欢 pandas"]
    assert added == 1

    # 超条数丢最旧
    merged, _ = merge_facts([f"旧{i}" for i in range(100)], ["新1"], 100, 100000)
    assert merged[0] == "旧1" and merged[-1] == "新1" and len(merged) == 100

    # 超字数继续丢（至少留 1 条）
    merged, _ = merge_facts(["短"], ["超" * 3000], 100, 2000)
    assert len(merged) == 1


# ---------------- should_fold ----------------

def test_should_fold(monkeypatch):
    import config.settings as cs
    monkeypatch.setattr(cs, "MEMORY_FOLD_MIN_MESSAGES", 5)
    monkeypatch.setattr(cs, "MEMORY_FOLD_MIN_CHARS", 800)
    assert should_fold(5, 0) is True
    assert should_fold(0, 900) is True
    assert should_fold(1, 100) is False
    assert should_fold(4, 799) is False


# ---------------- fold_material 编排（monkeypatch LLM） ----------------

def test_fold_material_ok_and_forget(monkeypatch):
    import yuanai_core.memory as mem
    monkeypatch.setattr(mem, "_call_fold_llm",
                        lambda sys, txt: "- 用户怕辣\n- 在做跨境电商")

    msgs = [{"role": "user", "content": "我怕辣"}, {"role": "assistant", "content": "好的"}]
    r = mem.fold_material("", msgs, 0, 2, set())
    assert r["ok"] is True
    assert r["facts"] == ["用户怕辣", "在做跨境电商"]
    assert r["k"] == 2

    # LLM 空输出 = 遗忘语义（ok 但 facts 空）
    monkeypatch.setattr(mem, "_call_fold_llm", lambda sys, txt: "")
    r = mem.fold_material("", msgs, 0, 2, set())
    assert r["ok"] is True and r["facts"] == []


def test_fold_material_llm_failure_keeps_cursor(monkeypatch):
    import yuanai_core.memory as mem
    monkeypatch.setattr(mem, "_call_fold_llm",
                        lambda sys, txt: (_ for _ in ()).throw(TimeoutError("timeout")))
    msgs = [{"role": "user", "content": "x"}]
    r = mem.fold_material("", msgs, 0, 1, set())
    assert r["ok"] is False
    assert "llm_failed" in r["reason"]


if __name__ == "__main__":
    print("测试入口：pytest test/test_memory_pure.py -v")
