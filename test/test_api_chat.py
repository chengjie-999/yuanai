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

        # 保存消息
        resp = client.post("/api/v1/chat/save", json={
            "session_id": session_id,
            "role": "user",
            "content": "你好，这是一条测试消息",
        }, headers=auth_headers)
        assert resp.status_code == 200


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
