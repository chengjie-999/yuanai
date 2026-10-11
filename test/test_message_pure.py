# -*- coding: utf-8 -*-
"""消息信封纯函数测试 — encode/decode/assign_turns（零 DB 零 LLM）

运行：pytest test/test_message_pure.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from yuanai_core.core.message import (  # noqa: E402
    Envelope, split_meta, decode, encode, strip, assign_turns, META_PREFIX,
)


def test_split_meta_roundtrip():
    meta, body = split_meta("\x00META\x00{\"s\":\"analysis\"}\x00正文")
    assert meta == {"s": "analysis"} and body == "正文"
    # 无前缀
    assert split_meta("普通消息") == ({}, "普通消息")
    # 坏 JSON 容错
    assert split_meta("\x00META\x00not-json\x00正文") == ({}, "\x00META\x00not-json\x00正文")
    # 无终止符
    assert split_meta("\x00META\x00{\"s\":\"x\"}") == ({}, "\x00META\x00{\"s\":\"x\"}")


def test_encode_decode_roundtrip():
    env = Envelope(sender="analysis", recipient="orchestrator", turn=3, type="summary")
    content = encode("分析结果", env)
    assert content.startswith(META_PREFIX)
    env2, body = decode(content)
    assert env2 == env and body == "分析结果"


def test_encode_default_no_prefix():
    assert encode("纯文本") == "纯文本"
    assert encode("纯文本", Envelope()) == "纯文本"
    # 默认 type=chat 不写短键
    assert encode("x", Envelope(sender="claude")) == "\x00META\x00{\"s\": \"claude\"}\x00x"


def test_encode_preserves_extra_meta():
    """前端既有 t/r/p 键原样保留（工具卡/推理/页面链接）"""
    extra = {"t": [{"name": "x", "status": "done"}], "r": "思考过程", "p": "/chat/agent/analysis"}
    content = encode("正文", Envelope(sender="analysis"), extra)
    meta, body = split_meta(content)
    assert body == "正文"
    assert meta["s"] == "analysis" and meta["t"] == extra["t"]
    assert meta["r"] == "思考过程" and meta["p"] == "/chat/agent/analysis"


def test_frontend_real_sample_compat():
    """真实前端样例串（旧格式）双向兼容：s 进信封，t/r 保留在 meta"""
    raw = '\x00META\x00{"s":"analysis","t":[{"name":"delegate_to_analysis_agent","status":"done"}],"r":"...","p":"/chat/agent/analysis"}\x00分析完成'
    env, body = decode(raw)
    assert env.sender == "analysis" and body == "分析完成"
    meta, _ = split_meta(raw)
    assert meta["t"] and meta["r"] and meta["p"]


def test_strip():
    assert strip("\x00META\x00{\"s\":\"x\"}\x00内容") == "内容"
    assert strip("无前缀") == "无前缀"
    assert strip("") == ""


def test_assign_turns():
    msgs = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "assistant", "content": "a1b"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "a2"},
    ]
    assign_turns(msgs)
    assert [m["turn"] for m in msgs] == [1, 1, 1, 2, 2]
    assert assign_turns([]) == []


def test_from_any_field_and_short_keys():
    assert Envelope.from_any({"sender": "a", "recipient": "b", "turn": 2, "type": "note"}) \
        == Envelope(sender="a", recipient="b", turn=2, type="note")
    assert Envelope.from_any({"s": "a", "rp": "b", "tn": 2, "ty": "note"}) \
        == Envelope(sender="a", recipient="b", turn=2, type="note")
    assert Envelope.from_any(None) == Envelope()
    assert Envelope.from_any({"sender": "a", "turn": "bad"}) == Envelope(sender="a", turn=0)
