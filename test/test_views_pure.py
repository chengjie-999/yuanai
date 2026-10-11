# -*- coding: utf-8 -*-
"""视图滤波纯函数测试 — view_for 规则矩阵（零 DB 零 LLM）

运行：pytest test/test_views_pure.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from yuanai_core.core.views import (  # noqa: E402
    view_for, compose_target_prompt, render_label, SUMMARY_CHARS, TOOL_RESULT_CHARS,
)


def test_render_label():
    assert render_label("analysis") == "【数据分析 Agent】"
    assert render_label("unknown_agent") == ""
    assert render_label("") == ""


def test_rule_matrix_self_and_directed():
    """规则 3/4/7：自己的话原样、别人对我说加前缀、别人对话摘要"""
    msgs = [
        {"role": "user", "content": "帮我分析"},
        {"role": "assistant", "content": "我来委派分析", "sender": "orchestrator"},
        {"role": "assistant", "content": "分析结果是……", "sender": "analysis", "recipient": "orchestrator"},
        {"role": "assistant", "content": "好的", "sender": "claude"},
    ]
    view = view_for("orchestrator", msgs)
    assert view[0] == {"role": "user", "content": "帮我分析"}
    assert view[1] == {"role": "assistant", "content": "我来委派分析"}
    assert view[2]["content"] == "【数据分析 Agent】分析结果是……"
    # claude 的话没对我说 → 摘要（无截断省略号）
    assert view[3]["content"] == "【Claude Code】好的"


def test_rule_user_directed_elsewhere_summarized():
    """规则 2：用户定向别人的消息 → 摘要"""
    msgs = [
        {"role": "user", "content": "请分析数据集", "recipient": "analysis"},
        {"role": "assistant", "content": "分析中", "sender": "analysis"},
    ]
    view = view_for("orchestrator", msgs)
    assert view[0]["content"].startswith("【用户@数据分析 Agent】")
    assert view[0]["content"].endswith("请分析数据集")


def test_rule_tool_result_truncated():
    """规则 5：tool_result 截断 + 标注"""
    long_out = "数据" * 1000
    msgs = [{"role": "assistant", "content": long_out, "sender": "analysis",
             "type": "tool_result"}]
    view = view_for("orchestrator", msgs)
    assert view[0]["content"].startswith("【数据分析 Agent】工具结果：")
    assert len(view[0]["content"]) <= len("【数据分析 Agent】工具结果：") + TOOL_RESULT_CHARS


def test_rule_summary_passthrough():
    msgs = [{"role": "assistant", "content": "总结内容", "sender": "analysis", "type": "summary"}]
    view = view_for("orchestrator", msgs)
    assert view[0]["content"] == "总结内容"


def test_envelopes_param_priority():
    """envelopes 参数优先于 dict 字段"""
    msgs = [{"role": "assistant", "content": "话", "sender": "claude"}]
    view = view_for("orchestrator", msgs,
                    envelopes=[{"sender": "analysis", "recipient": "orchestrator"}])
    assert view[0]["content"] == "【数据分析 Agent】话"


def test_degrade_passthrough_when_no_envelope():
    """全空信封 → 退化直通（仅剥 META）"""
    msgs = [
        {"role": "user", "content": "普通消息"},
        {"role": "assistant", "content": "\x00META\x00{\"s\":\"analysis\"}\x00旧数据"},
    ]
    view = view_for("orchestrator", msgs)
    assert view[0]["content"] == "普通消息"
    assert view[1]["content"] == "旧数据"


def test_length_mismatch_degrade():
    """envelopes 与 messages 长度不一致 → 不崩，按可用部分解析"""
    msgs = [{"role": "user", "content": "hi"}]
    view = view_for("orchestrator", msgs, envelopes=[{"sender": "x"}])
    assert view[0]["content"] == "hi"


def test_tool_calls_passthrough():
    msgs = [{"role": "assistant", "content": "", "sender": "orchestrator",
             "tool_calls": [{"name": "list_datasets", "arguments": "{}"}]}]
    view = view_for("orchestrator", msgs)
    assert view[0]["tool_calls"] == msgs[0]["tool_calls"]


def test_self_senders_local():
    """local 模式：orchestrator 视角把自己和 local 都当自己"""
    msgs = [
        {"role": "assistant", "content": "本机说的话", "sender": "local"},
        {"role": "assistant", "content": "别的话", "sender": "analysis"},
    ]
    view = view_for("orchestrator", msgs, self_senders={"local"})
    assert view[0]["content"] == "本机说的话"
    assert view[1]["content"] == "【数据分析 Agent】别的话"


def test_compose_target_prompt():
    view = [
        {"role": "user", "content": "第一次问"},
        {"role": "assistant", "content": "第一次答"},
        {"role": "user", "content": "分析数据集"},
        {"role": "assistant", "content": "", "tool_calls": [{"name": "x"}]},
    ]
    prompt = compose_target_prompt(view, max_context=1)
    assert "分析数据集" in prompt  # 最新 user 正文
    assert "第一次答" in prompt     # 最近一条上下文
    assert "第一次问" not in prompt  # max_context=1 截断更早的
    # 工具结构行不进 prompt
    assert "tool_calls" not in prompt


def test_compose_target_prompt_empty():
    assert compose_target_prompt([]) == ""
    assert compose_target_prompt([{"role": "user", "content": "只有一条"}]) == "只有一条"
