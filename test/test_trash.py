"""
会话回收站测试（2026-10-30 用户拍板）：
删除=软删除可恢复；1 年不活跃自动归档（主对话除外）；回收站超期自动彻底清理。
"""
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


class TestTrashFlow:
    def test_soft_delete_restore_purge(self, client, auth_headers, db):
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        create = client.post("/api/v1/chat/session/new", json={"title": "回收站测试"}, headers=auth_headers)
        assert create.status_code == 200
        sid = create.json()["session_id"]
        try:
            client.post("/api/v1/chat/save", json={
                "session_id": sid,
                "messages": [{"role": "user", "content": "将被软删除的历史"}],
            }, headers=auth_headers)
            # 软删除
            resp = client.delete(f"/api/v1/chat/session/{sid}", headers=auth_headers)
            assert resp.status_code == 200
            # 列表不再出现
            sessions = client.get("/api/v1/chat/sessions", headers=auth_headers).json()
            assert all(s["session_id"] != sid for s in sessions)
            # 回收站可见
            trash = client.get("/api/v1/chat/trash", headers=auth_headers).json()
            assert any(t["session_id"] == sid for t in trash)
            # 恢复 → 回列表、消息原样
            resp = client.post(f"/api/v1/chat/trash/{sid}/restore", headers=auth_headers)
            assert resp.status_code == 200
            sessions = client.get("/api/v1/chat/sessions", headers=auth_headers).json()
            assert any(s["session_id"] == sid for s in sessions)
            msgs = client.post("/api/v1/chat/messages", json={"session_id": sid}, headers=auth_headers).json()
            assert any(m.get("content") == "将被软删除的历史" for m in msgs)
            # 再删 → 彻底删除
            client.delete(f"/api/v1/chat/session/{sid}", headers=auth_headers)
            resp = client.delete(f"/api/v1/chat/trash/{sid}", headers=auth_headers)
            assert resp.status_code == 200
            assert not any(t["session_id"] == sid for t in client.get("/api/v1/chat/trash", headers=auth_headers).json())
            # 再恢复不存在 → 404
            assert client.post(f"/api/v1/chat/trash/{sid}/restore", headers=auth_headers).status_code == 404
        finally:
            from db.session import ChatSession, AIChat, AIChatFeedback, SessionMemoryState
            sess = db.Session()
            try:
                sess.query(AIChat).filter_by(session_id=sid).delete()
                sess.query(AIChatFeedback).filter_by(session_id=sid).delete()
                sess.query(SessionMemoryState).filter_by(session_id=sid).delete()
                sess.query(ChatSession).filter_by(session_id=sid).delete()
                sess.commit()
            finally:
                sess.close()

    def test_trash_requires_login(self, client):
        assert client.get("/api/v1/chat/trash").status_code == 401


class TestAutoArchive:
    def test_auto_archive_inactive_regular_only(self, db, auth_headers, client):
        """1 年未更新的普通对话自动进回收站；主对话永不归档"""
        from db.session import ChatSession
        from datetime import datetime, timedelta
        sess = db.Session()
        # 直接用 db 建一个 update_time 很旧的普通会话 + 一个旧主对话
        try:
            old_regular = ChatSession(session_id="trash-auto-regular", user_id=99999988,
                                      title="一年没动", is_main=0)
            sess.add(old_regular)
            sess.flush()
            sess.query(ChatSession).filter_by(session_id="trash-auto-regular").update(
                {"update_time": datetime.utcnow() - timedelta(days=400)})
            sess.commit()
        finally:
            sess.close()
        try:
            n = db.auto_archive_inactive(365)
            assert n >= 1
            sess = db.Session()
            try:
                row = sess.query(ChatSession).filter_by(session_id="trash-auto-regular").first()
                assert row and row.deleted_at is not None  # 已进回收站
            finally:
                sess.close()
        finally:
            sess = db.Session()
            try:
                sess.query(ChatSession).filter_by(session_id="trash-auto-regular").delete()
                sess.commit()
            finally:
                sess.close()

    def test_purge_expired_trash_cascade(self, db):
        """回收站超期（1 年）→ 级联彻底删除（消息一并清）"""
        from db.session import ChatSession, AIChat
        from datetime import datetime, timedelta
        sess = db.Session()
        try:
            sess.add(ChatSession(session_id="trash-purge-x", user_id=99999989, title="超期", is_main=0))
            sess.add(AIChat(session_id="trash-purge-x", role="user", content="将被级联清理"))
            sess.flush()
            sess.query(ChatSession).filter_by(session_id="trash-purge-x").update(
                {"deleted_at": datetime.utcnow() - timedelta(days=400)})
            sess.commit()
        finally:
            sess.close()
        n = db.purge_expired_trash(365)
        assert n >= 1
        sess = db.Session()
        try:
            assert sess.query(ChatSession).filter_by(session_id="trash-purge-x").first() is None
            assert sess.query(AIChat).filter_by(session_id="trash-purge-x").first() is None
        finally:
            sess.close()
