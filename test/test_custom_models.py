"""用户自持自定义模型测试（2026-11-15，迁移 0034：个人主体最稳定最合规通道）。

覆盖：端点鉴权/脱敏/加密存储/结构校验/上限；get_llm 用户级读取（ContextVar）；
C9 出境放行仅限用户显式确认。零真实网络（lc 测试只测 _get_user_custom_model）。"""

import asyncio
import json

import pytest


@pytest.fixture
def enc_pwd(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_PASSWORD", "test-enc-pwd")


def _put(client, headers, models, new_keys=None):
    return client.put("/api/v1/auth/custom-models",
                      json={"models": models, "new_keys": new_keys or {}},
                      headers=headers)


def test_custom_models_requires_login(client):
    assert client.get("/api/v1/auth/custom-models").status_code == 401
    assert client.put("/api/v1/auth/custom-models", json={"models": []}).status_code == 401


def test_custom_models_roundtrip_masked(client, auth_headers, enc_pwd):
    if not auth_headers:
        pytest.skip("需要有效登录凭据")
    # 添加（key 加密存储）
    resp = _put(client, auth_headers,
                [{"name": "my-claude", "base_url": "https://api.anthropic.com",
                  "overseas": True}],
                {"my-claude": "sk-test-123"})
    assert resp.status_code == 200
    # GET 脱敏：has_key=True、无明文 key
    data = client.get("/api/v1/auth/custom-models", headers=auth_headers).json()
    assert any(m["name"] == "my-claude" and m["has_key"] for m in data["models"])
    assert "sk-test-123" not in json.dumps(data)
    # 库内密文非明文
    from db.session import get_db, User
    db = get_db()
    with db.session() as sess:
        row = sess.query(User).filter_by(username="__test_api_user__").first()
        raw = row.custom_models
    assert "sk-test-123" not in raw
    # 修改不传 key → 保留密文（has_key 仍 True）
    resp = _put(client, auth_headers,
                [{"name": "my-claude", "base_url": "https://api.anthropic.com",
                  "overseas": True}])
    assert resp.status_code == 200
    data = client.get("/api/v1/auth/custom-models", headers=auth_headers).json()
    assert data["models"][0]["has_key"] is True
    # 删除
    _put(client, auth_headers, [])
    data = client.get("/api/v1/auth/custom-models", headers=auth_headers).json()
    assert data["models"] == []


def test_custom_models_validation(client, auth_headers, enc_pwd):
    if not auth_headers:
        pytest.skip("需要有效登录凭据")
    # 非法名/非法 URL 被滤掉；空 key 且无旧密文仍可存（has_key=False）
    resp = _put(client, auth_headers,
                [{"name": "非法名!!", "base_url": "https://x.com", "overseas": False},
                 {"name": "ok-model", "base_url": "ftp://bad", "overseas": False}])
    assert resp.status_code == 200
    data = client.get("/api/v1/auth/custom-models", headers=auth_headers).json()
    assert data["models"] == []
    # 上限 5 个
    models = [{"name": f"m{i}", "base_url": "https://x.com", "overseas": False}
              for i in range(7)]
    resp = _put(client, auth_headers, models)
    data = client.get("/api/v1/auth/custom-models", headers=auth_headers).json()
    assert len(data["models"]) == 5
    _put(client, auth_headers, [])


def test_get_user_custom_model_lookup(monkeypatch, enc_pwd):
    """lc 用户级读取：ContextVar uid + 库内加密配置 → (key, base_url, overseas)"""
    from yuanai_core.core import lc
    from utils.sensitive_data import encrypt_sensitive_data

    class FakeRow:
        custom_models = json.dumps([{
            "name": "my-claude", "base_url": "https://api.anthropic.com",
            "overseas": True,
            "key_encrypted": encrypt_sensitive_data("sk-user-key", "test-enc-pwd"),
        }])

    class FakeSess:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def query(self, model):
            return self

        def filter_by(self, **kw):
            return self

        def first(self):
            return FakeRow()

    class FakeDB:
        def session(self):
            return FakeSess()

    monkeypatch.setattr(lc, "current_llm_user_id",
                        lc.ContextVar("lc_user_id", default=0))
    lc.current_llm_user_id.set(42)
    import db.session as db_mod
    monkeypatch.setattr(db_mod, "get_db", lambda: FakeDB())

    out = lc._get_user_custom_model("my-claude")
    assert out == ("sk-user-key", "https://api.anthropic.com", True)
    assert lc._get_user_custom_model("unknown") is None
    # 未设 uid → None（回落全局配置）
    lc.current_llm_user_id.set(0)
    assert lc._get_user_custom_model("my-claude") is None
