# -*- coding: utf-8 -*-
"""#30 消息 id 测试（2026-11-14）：保存幂等化——增量 upsert/显式删除/旧客户端兼容"""
import uuid

import pytest


def _db_or_skip():
    try:
        from db.session import get_db
        return get_db()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


@pytest.fixture(scope="module")
def db():
    return _db_or_skip()


def _sid():
    return f"msgid-{uuid.uuid4().hex[:12]}"


def _cleanup(db, sid):
    from db.session import AIChat, AIChatFeedback, SessionMemoryState, ChatSession
    sess = db.Session()
    try:
        sess.query(AIChat).filter_by(session_id=sid).delete()
        sess.query(AIChatFeedback).filter_by(session_id=sid).delete()
        sess.query(SessionMemoryState).filter_by(session_id=sid).delete()
        sess.query(ChatSession).filter_by(session_id=sid).delete()
        sess.commit()
    finally:
        sess.close()


def _save(client, h, sid, messages, deleted_ids=None):
    body = {"session_id": sid, "messages": messages}
    if deleted_ids is not None:
        body["deleted_ids"] = deleted_ids
    return client.post("/api/v1/chat/save", json=body, headers=h)


def _load(client, h, sid):
    return client.post("/api/v1/chat/messages", json={"session_id": sid}, headers=h).json()


def _mk(content, mid=None, role="user"):
    m = {"role": role, "content": content}
    if mid:
        m["msg_id"] = mid
    return m


class TestMessageId:
    def test_incremental_upsert_idempotent(self, client, auth_headers, db):
        """带 id 保存幂等：同 id 重复保存不重复；新增消息不删已有消息（旧快照晚到不覆盖）"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        sid = _sid()
        client.post("/api/v1/chat/session/new", json={"title": "id 测试"}, headers=auth_headers)
        try:
            a, b, c = [uuid.uuid4().hex for _ in range(3)]
            # 第一轮：A、B
            assert _save(client, auth_headers, sid, [_mk("一", a), _mk("二", b)]).status_code == 200
            # 第二轮（另一端的旧快照）：B、C——B 已存在跳过，C 新增；A 不删
            assert _save(client, auth_headers, sid, [_mk("二", b), _mk("三", c)]).status_code == 200
            rows = _load(client, auth_headers, sid)
            mids = {r.get("msg_id") for r in rows}
            assert mids == {a, b, c}  # 无重复、无覆盖丢失
            assert len(rows) == 3
        finally:
            _cleanup(db, sid)

    def test_explicit_delete(self, client, auth_headers, db):
        """deleted_ids 显式删除（编辑重发截断）"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        sid = _sid()
        client.post("/api/v1/chat/session/new", json={"title": "id 删除测试"}, headers=auth_headers)
        try:
            a, b, c = [uuid.uuid4().hex for _ in range(3)]
            _save(client, auth_headers, sid, [_mk("一", a), _mk("二", b), _mk("三", c)])
            _save(client, auth_headers, sid, [_mk("一", a)], deleted_ids=[b, c])
            rows = _load(client, auth_headers, sid)
            assert {r.get("msg_id") for r in rows} == {a}
        finally:
            _cleanup(db, sid)

    def test_legacy_no_id_full_replace(self, client, auth_headers, db):
        """旧客户端（消息不带 id）→ 全量替换兼容路径"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        sid = _sid()
        client.post("/api/v1/chat/session/new", json={"title": "id 兼容测试"}, headers=auth_headers)
        try:
            _save(client, auth_headers, sid, [_mk("一"), _mk("二")])
            _save(client, auth_headers, sid, [_mk("三")])
            rows = _load(client, auth_headers, sid)
            assert [r.get("content") for r in rows] == ["三"]  # 全量替换
            assert rows[0].get("msg_id") == ""  # 旧数据无 id
        finally:
            _cleanup(db, sid)
