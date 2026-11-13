"""
多智能体窗口 P0 测试（2026-11-13）：会话 agent_kind 打标与执行窗口隔离。

覆盖：创建打标/列表过滤/非法值 400/执行窗口跳过记忆折叠/执行窗口禁止分享/
旧 @私聊会话标题推断回填（迁移 0031）。
"""
import importlib
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


def _cleanup(db, sid):
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


class TestSessionAgentKind:
    def test_create_and_filter_by_kind(self, client, auth_headers, db):
        """claude 会话创建即打标；sessions?agent_kind= 只返回该类会话"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        cc = client.post("/api/v1/chat/session/new",
                         json={"title": "CC 执行测试", "agent_kind": "claude"},
                         headers=auth_headers)
        assert cc.status_code == 200
        assert cc.json()["agent_kind"] == "claude"
        chat = client.post("/api/v1/chat/session/new",
                           json={"title": "普通对话测试"}, headers=auth_headers)
        assert chat.status_code == 200
        assert chat.json()["agent_kind"] == "chat"
        cc_sid, chat_sid = cc.json()["session_id"], chat.json()["session_id"]
        try:
            all_sessions = client.get("/api/v1/chat/sessions?own=1",
                                      headers=auth_headers).json()
            all_sids = {s["session_id"] for s in all_sessions}
            assert cc_sid in all_sids and chat_sid in all_sids
            kind_sessions = client.get("/api/v1/chat/sessions?own=1&agent_kind=claude",
                                       headers=auth_headers).json()
            kind_sids = {s["session_id"] for s in kind_sessions}
            assert cc_sid in kind_sids
            assert chat_sid not in kind_sids
            assert all(s["agent_kind"] == "claude" for s in kind_sessions)
        finally:
            _cleanup(db, cc_sid)
            _cleanup(db, chat_sid)

    def test_invalid_kind_rejected(self, client, auth_headers):
        """非法 agent_kind：创建与会话过滤均 400（白名单 fail-closed）"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        resp = client.post("/api/v1/chat/session/new",
                           json={"title": "x", "agent_kind": "hacker"},
                           headers=auth_headers)
        assert resp.status_code == 400
        resp = client.get("/api/v1/chat/sessions?own=1&agent_kind=hacker",
                          headers=auth_headers)
        assert resp.status_code == 400

    def test_agent_session_skips_memory_fold(self, client, auth_headers, db, monkeypatch):
        """执行窗口会话保存不触发记忆折叠；对话窗口仍触发（多窗口 D5）"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        calls = []
        monkeypatch.setattr("api.v1.chat.memory_fold.maybe_schedule_memory_fold",
                            lambda *a, **k: calls.append(a))
        monkeypatch.setattr("api.v1.chat.memory_organize.maybe_schedule_memory_organize",
                            lambda *a, **k: calls.append(("organize", a)))
        monkeypatch.setattr("api.v1.chat.title_gen.maybe_generate_title",
                            lambda *a, **k: calls.append(("title", a)))
        cc = client.post("/api/v1/chat/session/new",
                         json={"title": "CC 折叠测试", "agent_kind": "claude"},
                         headers=auth_headers).json()
        chat = client.post("/api/v1/chat/session/new",
                           json={"title": "对话折叠测试"}, headers=auth_headers).json()
        try:
            msgs = [{"role": "user", "content": "x" * 100},
                    {"role": "assistant", "content": "y" * 100}]
            client.post("/api/v1/chat/save", json={"session_id": cc["session_id"],
                                                   "messages": msgs},
                        headers=auth_headers)
            assert calls == []  # 执行窗口：折叠/整理/标题全不触发
            client.post("/api/v1/chat/save", json={"session_id": chat["session_id"],
                                                   "messages": msgs},
                        headers=auth_headers)
            assert any(len(a) == 4 and a[0] == chat["session_id"] for a in calls)
        finally:
            _cleanup(db, cc["session_id"])
            _cleanup(db, chat["session_id"])

    def test_agent_session_share_rejected(self, client, auth_headers, db):
        """执行窗口会话禁止分享（多窗口 D4）；对话窗口不受影响"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        cc = client.post("/api/v1/chat/session/new",
                         json={"title": "CC 分享测试", "agent_kind": "claude"},
                         headers=auth_headers).json()
        chat = client.post("/api/v1/chat/session/new",
                           json={"title": "对话分享测试"}, headers=auth_headers).json()
        try:
            msgs = [{"role": "user", "content": "分享内容"}]
            client.post("/api/v1/chat/save", json={"session_id": cc["session_id"],
                                                   "messages": msgs},
                        headers=auth_headers)
            resp = client.post(f"/api/v1/chat/share/{cc['session_id']}", headers=auth_headers)
            assert resp.status_code == 400
            assert "分享" in resp.json()["detail"]
            # 对话窗口仍可分享（回归：分享功能不受 agent_kind 收口影响）
            client.post("/api/v1/chat/save", json={"session_id": chat["session_id"],
                                                   "messages": msgs},
                        headers=auth_headers)
            resp = client.post(f"/api/v1/chat/share/{chat['session_id']}", headers=auth_headers)
            assert resp.status_code == 200
            client.delete(f"/api/v1/chat/share/{chat['session_id']}", headers=auth_headers)
        finally:
            _cleanup(db, cc["session_id"])
            _cleanup(db, chat["session_id"])


class TestLegacyKindBackfill:
    def test_infer_legacy_kind(self):
        m = importlib.import_module("db.migrations.versions.0031_add_session_agent_kind")
        assert m.infer_legacy_kind("Claude Code 私聊") == "claude"
        assert m.infer_legacy_kind("自动化 Agent 私聊") == "automation"
        assert m.infer_legacy_kind("普通对话") == "chat"
        assert m.infer_legacy_kind("Claude Code") == "chat"  # 非私聊形态不误标

    def test_backfill_updates_legacy_titles(self, db):
        """旧 @私聊会话按标题推断回填；普通会话不动；幂等（重跑结果一致）"""
        from db.session import ChatSession
        sids = [f"kind-backfill-{uuid.uuid4().hex[:12]}" for _ in range(3)]
        sess = db.Session()
        try:
            sess.add(ChatSession(session_id=sids[0], user_id=99999988,
                                 title="Claude Code 私聊"))
            sess.add(ChatSession(session_id=sids[1], user_id=99999988,
                                 title="自动化 Agent 私聊"))
            sess.add(ChatSession(session_id=sids[2], user_id=99999988,
                                 title="普通对话"))
            sess.commit()
        finally:
            sess.close()
        try:
            m = importlib.import_module("db.migrations.versions.0031_add_session_agent_kind")
            # alembic 侧 op.get_bind() 给的是 Connection；Engine 无 execute（SQLAlchemy 2.x）
            with db.engine.connect() as conn:
                assert m.backfill_legacy_kinds(conn) == 2
            sess = db.Session()
            try:
                rows = {r.session_id: r.agent_kind
                        for r in sess.query(ChatSession)
                        .filter(ChatSession.session_id.in_(sids)).all()}
            finally:
                sess.close()
            assert rows[sids[0]] == "claude"
            assert rows[sids[1]] == "automation"
            assert rows[sids[2]] == "chat"
            # 幂等：再跑一遍（chat 行已非私聊 → 返回 0，结果不变）
            with db.engine.connect() as conn:
                assert m.backfill_legacy_kinds(conn) == 0
        finally:
            for sid in sids:
                _cleanup(db, sid)
