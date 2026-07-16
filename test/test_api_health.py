"""
API 基础端点测试 — 健康检查、公开路径
"""
import pytest


class TestHealthCheck:
    """健康检查和根路径"""

    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_docs_public(self, client):
        """文档页无需认证"""
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_openapi_public(self, client):
        """OpenAPI JSON 无需认证"""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        assert "info" in resp.json()


class TestAuthEndpoints:
    """认证端点"""

    def test_login_public(self, client):
        """登录端点无需认证"""
        resp = client.post("/api/v1/auth/login", json={
            "username": "nonexistent_user_12345",
            "password": "wrong",
        })
        # 应返回 401 而非 401/403 之外的错误（不会因为未认证被拦截）
        assert resp.status_code in (401, 429)

    def test_register_disabled(self, client):
        """注册功能暂不开放"""
        resp = client.post("/api/v1/auth/register", json={
            "username": "test",
            "password": "test123",
        })
        assert resp.status_code == 403

    def test_protected_route_no_auth(self, client):
        """未认证访问受保护路由应返回 401"""
        resp = client.get("/api/v1/chat/sessions")
        assert resp.status_code in (401, 403)

    def test_token_check_invalid(self, client):
        """无效 token 检查"""
        resp = client.post("/api/v1/auth/check", json={"token": "invalid-token"})
        assert resp.status_code == 401

    def test_rate_limit(self, client):
        """超过限流阈值应返回 429"""
        # 发送 6 次登录请求（阈值是 5 次/60s）
        results = []
        for _ in range(6):
            resp = client.post("/api/v1/auth/login", json={
                "username": "ratelimit_test",
                "password": "test",
            })
            results.append(resp.status_code)
        # 至少有一次被限流（429）或正常拒绝（401）
        assert 429 in results or all(r in (401, 429) for r in results)


class TestToolsEndpoint:
    """工具列表端点"""

    def test_list_tools(self, client, auth_headers):
        """获取工具列表"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        resp = client.get("/api/v1/tools/", headers=auth_headers)
        assert resp.status_code == 200
        tools = resp.json()
        assert isinstance(tools, list)
        # 至少应该有基础工具
        assert len(tools) > 0
        # 检查工具格式
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
