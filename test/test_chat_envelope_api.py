# -*- coding: utf-8 -*-
"""信封落库 API 测试 — /chat/save 落列、get_chats 返回、turn 推导、语音路径混写

端点测试需要 MySQL（不可用则跳过）。运行：pytest test/test_chat_envelope_api.py -v
"""
import sys
import os
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from db.session import get_db  # noqa: E402


@pytest.fixture(scope="module")
def db():
    try:
        return get_db()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


@pytest.fixture(scope="module")
def session_id(db):
    sid = str(uuid.uuid4())
    sess = db.Session()
    try:
        from db.session import ChatSession
        sess.add(ChatSession(session_id=sid, title="env-test"))
        sess.commit()
    finally:
        sess.close()
    yield sid
    sess = db.Session()
    try:
        from db.session import AIChat, ChatSession
        sess.query(AIChat).filter_by(session_id=sid).delete()
        sess.query(ChatSession).filter_by(session_id=sid).delete()
        sess.commit()
    finally:
        sess.close()


def test_save_with_envelope_columns(db, session_id):
    """带信封保存 → 列值正确、turn 连续、META 正文无损"""
    messages = [
        {"role": "user", "content": "帮我分析", "sender": "user"},
        {"role": "assistant", "content": "好的", "sender": "orchestrator"},
        {"role": "assistant", "content": "分析完成", "sender": "analysis",
         "recipient": "orchestrator", "type": "summary"},
        {"role": "user", "content": "谢谢", "sender": "user"},
    ]
    sess = db.Session()
    try:
        from db.session import AIChat
        sess.query(AIChat).filter_by(session_id=session_id).delete()
        from yuanai_core.core.message import assign_turns
        assign_turns(messages)
        for m in messages:
            sess.add(AIChat(session_id=session_id, role=m["role"], content=m["content"],
                            sender=m.get("sender") or "", recipient=m.get("recipient") or "",
                            turn=m.get("turn") or 0, type=m.get("type") or "chat"))
        sess.commit()
    finally:
        sess.close()

    chats = db.get_chats(session_id)
    assert len(chats) == 4
    assert chats[0]["sender"] == "user" and chats[0]["turn"] == 1
    assert chats[1]["sender"] == "orchestrator" and chats[1]["turn"] == 1
    assert chats[2]["sender"] == "analysis" and chats[2]["recipient"] == "orchestrator"
    assert chats[2]["type"] == "summary" and chats[2]["turn"] == 1
    assert chats[3]["turn"] == 2
    # META 前缀正文无损
    meta_content = "\x00META\x00{\"s\":\"analysis\"}\x00分析完成"
    sess = db.Session()
    try:
        from db.session import AIChat
        sess.query(AIChat).filter_by(session_id=session_id).delete()
        sess.add(AIChat(session_id=session_id, role="assistant", content=meta_content,
                        sender="analysis", turn=1))
        sess.commit()
    finally:
        sess.close()
    chats = db.get_chats(session_id)
    assert chats[0]["content"] == meta_content and chats[0]["sender"] == "analysis"


def test_add_chat_voice_path_derives_envelope(db, session_id):
    """语音第二写路径：add_chat 推导 sender/turn，与 /save 混写后 turn 不倒退"""
    db.add_chat(session_id, "user", "语音问题")
    db.add_chat(session_id, "assistant", "语音回答")
    chats = db.get_chats(session_id)
    # 找到语音消息对
    voice = [c for c in chats if "语音" in c["content"]]
    assert len(voice) == 2
    assert voice[0]["sender"] == "user"
    assert voice[1]["sender"] == "orchestrator"
    assert voice[1]["turn"] == voice[0]["turn"]
    assert voice[1]["turn"] > 0
