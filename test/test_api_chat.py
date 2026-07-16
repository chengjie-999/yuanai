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
