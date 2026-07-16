"""
测试共享 fixtures — 使用 FastAPI TestClient + 内存数据库

安装依赖后运行：pip install -r requirements.txt && pytest test/ -v
"""
import os
import sys
import pytest

# 确保项目根在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture(scope="session")
def client():
    """
    FastAPI TestClient（需要完整环境：pip install -r requirements.txt）
    如果依赖未安装则跳过。
    """
    try:
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)
    except ImportError as e:
        pytest.skip(f"API 依赖未安装: {e}")


@pytest.fixture(scope="session")
def auth_headers(client):
    """登录并返回带 token 的 headers"""
    resp = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "admin123",
    })
    if resp.status_code == 200:
        token = resp.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    return {}
