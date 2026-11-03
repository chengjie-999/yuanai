"""
聊天 API 端点测试
"""
import pytest


class TestSessionManagement:
    """会话管理 CRUD"""

    def test_create_session(self, client, auth_headers):
        """创建新会话"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        resp = client.post("/api/v1/chat/session/new", json={
            "title": "测试会话",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["title"] == "测试会话"

    def test_list_sessions(self, client, auth_headers):
        """列出会话"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        resp = client.get("/api/v1/chat/sessions", headers=auth_headers)
        assert resp.status_code == 200
        sessions = resp.json()
        assert isinstance(sessions, list)

    def test_get_messages(self, client, auth_headers):
        """获取会话消息"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        # 先创建会话
        create_resp = client.post("/api/v1/chat/session/new", json={
            "title": "消息测试",
        }, headers=auth_headers)
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]

        # 获取消息（新会话应为空）
        resp = client.post("/api/v1/chat/messages", json={
            "session_id": session_id,
        }, headers=auth_headers)
        assert resp.status_code == 200
        messages = resp.json()
        assert isinstance(messages, list)

    def test_delete_session(self, client, auth_headers):
        """删除会话"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        # 先创建
        create_resp = client.post("/api/v1/chat/session/new", json={
            "title": "待删除",
        }, headers=auth_headers)
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]

        # 删除
        resp = client.delete(f"/api/v1/chat/session/{session_id}", headers=auth_headers)
        assert resp.status_code == 200


class TestChatSave:
    """消息保存"""

    def test_save_message(self, client, auth_headers):
        """保存一条聊天消息"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        # 创建会话
        create_resp = client.post("/api/v1/chat/session/new", json={
            "title": "保存测试",
        }, headers=auth_headers)
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]

        # 保存消息（现行协议：messages 数组全量替换；旧 role/content 单条协议已废弃）
        resp = client.post("/api/v1/chat/save", json={
            "session_id": session_id,
            "messages": [{"role": "user", "content": "你好，这是一条测试消息"}],
        }, headers=auth_headers)
        assert resp.status_code == 200

    def test_save_message_with_image(self, client, auth_headers):
        """保存带图片的消息（2026-11-04 事故锁死：缺 import re 曾致 NameError
        直穿 save 全量重建，整会话消息丢失、/chat/save 500）"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        create_resp = client.post("/api/v1/chat/session/new", json={
            "title": "图片保存测试",
        }, headers=auth_headers)
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]

        # 1x1 透明 PNG 的 data URL（真实前端形态）
        tiny_png = ("data:image/png;base64,"
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
                    "AAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
        resp = client.post("/api/v1/chat/save", json={
            "session_id": session_id,
            "messages": [
                {"role": "user", "content": "看看这张图", "images": [tiny_png]},
                {"role": "assistant", "content": "收到图片", "sender": "orchestrator"},
            ],
        }, headers=auth_headers)
        assert resp.status_code == 200

        # 图片应落盘为 /api/v1/chat/image/ 文件 URL，而非原样 data URL
        msgs = client.post("/api/v1/chat/messages", json={
            "session_id": session_id,
        }, headers=auth_headers).json()
        assert isinstance(msgs, list) and msgs
        # 消息形态兼容两种：dict（含 images 键）或含图片 URL 的序列化内容
        found = any(
            ("/api/v1/chat/image/" in str(m)) or
            (isinstance(m, dict) and any(
                str(i).startswith("/api/v1/chat/image/") for i in (m.get("images") or [])))
            for m in msgs
        )
        assert found, f"图片未落盘为文件 URL: {msgs}"


class TestHistoryEnvelope:
    """信封协议纯函数：_fix_history_for_api 透传 + _env_of（零 LLM 零 DB）"""

    def test_env_of_keeps_non_defaults(self):
        from api.v1.chat.router import _env_of
        assert _env_of({"sender": "analysis", "recipient": "orchestrator",
                        "turn": 3, "type": "summary", "content": "x"}) == {
            "sender": "analysis", "recipient": "orchestrator",
            "turn": 3, "type": "summary"}
        assert _env_of({"content": "x"}) == {}
        # turn=0 / type=chat（默认值）不保留
        assert _env_of({"turn": 0, "type": "chat"}) == {}

    def test_fix_history_passthrough_envelope(self):
        from api.v1.chat.router import _fix_history_for_api
        history = [
            {"role": "user", "content": "帮我分析"},
            {"role": "assistant", "content": "好的", "sender": "orchestrator",
             "tool_calls": [{"name": "delegate_to_analysis_agent", "arguments": "{}"}]},
            {"role": "tool", "content": "分析结果", "sender": "analysis",
             "type": "tool_result", "tool_call_id": "hist_0"},
        ]
        fixed = _fix_history_for_api(history)
        # tool 扁平化为 user，但信封透传
        assert fixed[2]["role"] == "user"
        assert fixed[2]["sender"] == "analysis"
        assert fixed[2]["type"] == "tool_result"
        # assistant 带 tool_calls 的拍平保留信封
        assert fixed[1]["sender"] == "orchestrator"
        assert "tool_calls" not in fixed[1]
        # user 原样
        assert fixed[0] == history[0]

    def test_fix_history_no_envelope_unchanged(self):
        from api.v1.chat.router import _fix_history_for_api
        history = [{"role": "user", "content": "hi"},
                   {"role": "assistant", "content": "hello"}]
        assert _fix_history_for_api(history) == history


def test_main_session_cannot_be_deleted(client, auth_headers):
    """主对话不可删除（2026-10-30 修复）：前端隐藏按钮 + 后端 400 拦截"""
    if not auth_headers:
        pytest.skip("需要有效登录凭据")
    r = client.post("/api/v1/chat/main-session", headers=auth_headers)
    assert r.status_code == 200
    sid = r.json()["session_id"]
    # 删除主对话 → 400
    resp = client.delete(f"/api/v1/chat/session/{sid}", headers=auth_headers)
    assert resp.status_code == 400
    assert "不可删除" in resp.json()["detail"]
    # 普通会话仍可删除
    create = client.post("/api/v1/chat/session/new", json={"title": "可删"}, headers=auth_headers)
    assert create.status_code == 200
    resp = client.delete(f"/api/v1/chat/session/{create.json()['session_id']}", headers=auth_headers)
    assert resp.status_code == 200


def test_demote_main_creates_new_main(client, auth_headers):
    """主对话降级（2026-10-30）：is_main=0 保留历史 + 自动新建空主对话"""
    if not auth_headers:
        pytest.skip("需要有效登录凭据")
    r = client.post("/api/v1/chat/main-session", headers=auth_headers)
    assert r.status_code == 200
    sid = r.json()["session_id"]
    # 发一条消息进主对话
    client.post("/api/v1/chat/save", json={
        "session_id": sid,
        "messages": [{"role": "user", "content": "历史消息"}],
    }, headers=auth_headers)
    # 降级
    resp = client.post("/api/v1/chat/demote-main", json={"session_id": sid}, headers=auth_headers)
    assert resp.status_code == 200
    new_sid = resp.json()["new_session_id"]
    assert new_sid != sid
    # 新主对话已创建
    r2 = client.post("/api/v1/chat/main-session", headers=auth_headers)
    assert r2.json()["session_id"] == new_sid
    # 旧对话历史保留且降级为普通
    msgs = client.post("/api/v1/chat/messages", json={"session_id": sid}, headers=auth_headers).json()
    assert any(m.get("content") == "历史消息" for m in msgs)
    sessions = client.get("/api/v1/chat/sessions", headers=auth_headers).json()
    old = [s for s in sessions if s["session_id"] == sid]
    assert old and not old[0].get("is_main")
    # 对普通会话再降级 → 400
    assert client.post("/api/v1/chat/demote-main", json={"session_id": sid},
                       headers=auth_headers).status_code == 400


def test_main_session_idempotent(client, auth_headers):
    """主对话幂等：连续调用返回同一条（2026-10-19 唯一性修复）"""
    if not auth_headers:
        pytest.skip("需要有效登录凭据")
    r1 = client.post("/api/v1/chat/main-session", headers=auth_headers)
    r2 = client.post("/api/v1/chat/main-session", headers=auth_headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["session_id"] == r2.json()["session_id"]
    assert r1.json()["is_main"] is True


def test_ensure_main_session_unique_constraint():
    """DB 层：唯一索引兜底——同用户第二条主对话被拒（并发竞态防线）"""
    import uuid as _uuid
    from sqlalchemy.exc import IntegrityError
    from db.session import get_db, ChatSession

    db = get_db()
    uid = 99999901  # 一次性临时用户
    sess = db.Session()
    try:
        sess.query(ChatSession).filter_by(user_id=uid).delete()
        sess.commit()
        r = db.ensure_main_session(uid)
        r2 = db.ensure_main_session(uid)
        assert r2["session_id"] == r["session_id"], "ensure 幂等：同一条主对话"
        sess.add(ChatSession(session_id=str(_uuid.uuid4()), user_id=uid, title="x", is_main=1))
        with pytest.raises(IntegrityError):
            sess.commit()
        sess.rollback()
    finally:
        sess.query(ChatSession).filter_by(user_id=uid).delete()
        sess.commit()
        sess.close()


class TestFollowupSuggestions:
    """追问预测（2026-10-31）：AI 预测用户接下来可能问的问题"""

    def test_parse_three_items(self, monkeypatch):
        import asyncio
        from api.v1.chat.router import _followup_suggestions

        class _FakeResp:
            content = "1. 什么是数据清洗\n2. 怎么处理缺失值\n3. 有什么工具推荐"

        class _FakeLLM:
            def invoke(self, msgs):
                return _FakeResp()

        monkeypatch.setattr("yuanai_core.core.lc.get_llm", lambda *a, **k: _FakeLLM())
        items = asyncio.run(_followup_suggestions("用户问了一些数据分析的问题，助手做了回答。" * 5))
        assert items == ["什么是数据清洗", "怎么处理缺失值", "有什么工具推荐"]

    def test_disabled_returns_empty(self, monkeypatch):
        import asyncio
        from api.v1.chat.router import _followup_suggestions
        monkeypatch.setattr("config.settings.FOLLOWUP_SUGGEST_ENABLED", False)
        assert asyncio.run(_followup_suggestions("足够长的对话内容" * 10)) == []

    def test_short_text_returns_empty(self):
        import asyncio
        from api.v1.chat.router import _followup_suggestions
        assert asyncio.run(_followup_suggestions("太短")) == []
