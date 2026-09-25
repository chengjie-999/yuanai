# -*- coding: utf-8 -*-
"""S3.3/S3.4 令牌安全测试 — token_version 吊销 / 老 token 兼容 / wss 强制 / 桥接令牌上限

运行：pytest test/test_token_revoke.py -v
端点测试需要 MySQL（不可用则跳过），其余离线可跑。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')


# ---------------- 离线：wss 强制 ----------------

def test_claude_bridge_rejects_plaintext_ws(monkeypatch):
    """ws:// 公网地址 → SystemExit；localhost + env 豁免 → 放行"""
    from agent import claude_bridge
    from agent import main as agent_main

    monkeypatch.setattr(agent_main, "load_identity", lambda: {})
    monkeypatch.delenv("AGENT_ALLOW_INSECURE_WS", raising=False)

    for bad in ("ws://cjyuanai.cn", "ws://192.168.1.5"):
        monkeypatch.setattr(sys, "argv", ["x", "--server-url", bad])
        with pytest.raises(SystemExit):
            claude_bridge.parse_args()

    # localhost 无 env 豁免 → 仍拒
    monkeypatch.setattr(sys, "argv", ["x", "--server-url", "ws://localhost:8000"])
    with pytest.raises(SystemExit):
        claude_bridge.parse_args()

    # localhost + env 豁免 → 放行
    monkeypatch.setenv("AGENT_ALLOW_INSECURE_WS", "1")
    monkeypatch.setattr(sys, "argv", ["x", "--server-url", "ws://localhost:8000"])
    args = claude_bridge.parse_args()
    assert args.server_url == "ws://localhost:8000"

    # wss 始终放行
    monkeypatch.setattr(sys, "argv", ["x", "--server-url", "wss://cjyuanai.cn"])
    args = claude_bridge.parse_args()
    assert args.server_url == "wss://cjyuanai.cn"


# ---------------- 离线：token_version 语义（自建 SQLite 库） ----------------

def _make_test_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from db.session import Base, AgentDatabase

    db = AgentDatabase.__new__(AgentDatabase)
    db.engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(db.engine)
    db._run_alembic_migrations = lambda: None
    db.Session = sessionmaker(bind=db.engine)
    return db


def test_token_payload_has_jti_and_tv():
    from api.v1.auth.utils import create_token, verify_token
    token = create_token(1, "user", tv=0)
    payload = verify_token(token)
    assert payload["user_id"] == 1
    assert payload["tv"] == 0
    assert payload.get("jti")  # 唯一标识


def test_legacy_token_without_tv_compatible():
    """老 token（无 tv 字段）解析后 tv 视为 0，token_version=0 时照常放行"""
    from jose import jwt
    from datetime import datetime, timedelta
    from api.v1.auth.utils import verify_token
    from config.settings import JWT_SECRET_KEY, JWT_ALGORITHM

    legacy = jwt.encode(
        {"user_id": 1, "role": "user", "exp": datetime.utcnow() + timedelta(days=1)},
        JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    payload = verify_token(legacy)
    assert int(payload.get("tv") or 0) == 0


def test_token_version_column_in_model():
    from db.session import User
    assert "token_version" in User.__table__.columns
    assert User.__table__.columns["token_version"].default.arg == 0


# ---------------- 端点（需要 MySQL） ----------------

def _db_or_skip():
    try:
        from db.session import get_db
        return get_db()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


@pytest.fixture(scope="module")
def db():
    return _db_or_skip()


def test_revoke_invalidates_tokens(client, db):
    """签发 → 200 → token_version+1 → 同 token 401（吊销生效）"""
    from db.session import User
    from api.v1.auth.utils import create_token

    r = db.register_user("__revoke_test__", "test123")
    uid = r["id"]
    token = create_token(uid, "user")

    def cleanup():
        sess = db.Session()
        try:
            u = sess.query(User).filter_by(id=uid).first()
            if u:
                sess.delete(u)
                sess.commit()
        finally:
            sess.close()

    try:
        # 正常访问
        resp = client.get("/api/v1/data/datasets", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, resp.text

        # 吊销（等价 admin 端点：token_version +1）
        sess = db.Session()
        try:
            u = sess.query(User).filter_by(id=uid).first()
            u.token_version = (u.token_version or 0) + 1
            sess.commit()
        finally:
            sess.close()

        # 旧 token 立即失效
        resp = client.get("/api/v1/data/datasets", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401, f"吊销未生效: {resp.status_code}"
    finally:
        cleanup()


def test_agent_token_cap_90_days(client, db):
    """桥接长令牌上限收敛：91 天 → 400"""
    from api.v1.auth.utils import create_token
    from db.session import User

    # 复用/自建 admin 测试用户（重复注册返回 error 亦可）
    db.register_user("__sse_admin_test__", "test123", role="admin")
    sess = db.Session()
    try:
        uid = sess.query(User).filter_by(username="__sse_admin_test__").first().id
    finally:
        sess.close()

    resp = client.post("/api/v1/admin/agent-token",
                       headers={"Authorization": f"Bearer {create_token(uid, 'admin')}"},
                       json={"user_id": uid, "expires_days": 91})
    assert resp.status_code == 400

    resp = client.post("/api/v1/admin/agent-token",
                       headers={"Authorization": f"Bearer {create_token(uid, 'admin')}"},
                       json={"user_id": uid, "expires_days": 90})
    assert resp.status_code == 200


if __name__ == "__main__":
    print("测试入口：pytest test/test_token_revoke.py -v")
