"""chat-token 端点测试（2026-11-12，#40 终端第三端）：设备凭据 → 绑定用户会话 JWT。

零网络——_verify_agent_secret mock，DB 直查；JWT 用 verify_token 本地解析。"""

import secrets

import pytest

from db.session import get_db


def _db_or_skip():
    try:
        return get_db()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


@pytest.fixture(scope="module")
def db():
    return _db_or_skip()


@pytest.fixture()
def authed(client, monkeypatch):
    """mock 设备凭据通过"""
    from api.v1.agent import router as ar
    monkeypatch.setattr(ar, "_verify_agent_secret", lambda aid, secret: True)


def _mk_dev(db, user_id=None):
    """注册测试设备（幂等随机码），返回设备 id"""
    from db.session import AgentDevice
    code = "YUAN-" + "-".join(secrets.token_hex(2).upper() for _ in range(3))
    with db.session() as sess:
        dev = AgentDevice(install_code=code, agent_secret="SECRET",
                          user_id=user_id, machine_name="我的电脑")
        sess.add(dev)
        sess.commit()
        return dev.id


def _h(dev_id):
    return {"X-Agent-Id": str(dev_id), "X-Agent-Secret": "SECRET"}


def test_chat_token_requires_creds(client):
    resp = client.post("/api/v1/agent/chat-token")
    assert resp.status_code == 401
    # middleware 放行由端点自鉴权——detail 必须是端点的凭据报错而非「未提供 token」
    assert "凭据" in resp.json()["detail"]


def test_chat_token_unbound_403(client, authed, db):
    dev_id = _mk_dev(db, user_id=None)
    resp = client.post("/api/v1/agent/chat-token", headers=_h(dev_id))
    assert resp.status_code == 403
    assert "未绑定" in resp.json()["detail"]


def test_chat_token_bound(client, authed, db):
    """已绑定设备 → 会话 JWT 可解析且用户正确（终端=第三端）"""
    from db.session import User
    from api.v1.auth.utils import verify_token
    r = db.register_user("__chat_token_user__", "test1234")
    if "error" in r:
        with db.session() as sess:
            uid = sess.query(User).filter_by(username="__chat_token_user__").first().id
    else:
        uid = r["id"]
    dev_id = _mk_dev(db, user_id=uid)
    resp = client.post("/api/v1/agent/chat-token", headers=_h(dev_id))
    assert resp.status_code == 200
    d = resp.json()
    assert d["user_id"] == uid
    assert d["username"] == "__chat_token_user__"
    payload = verify_token(d["token"])
    assert payload is not None
    assert payload["user_id"] == uid
    assert payload["role"] == "user"
    assert "sess" not in payload  # 不占浏览器登录会话数（与桥接长令牌同口径）


def test_chat_token_frozen_403(client, authed, db):
    """冻结账号 → 403 且文案含「冻结」（C7 与登录同口径）"""
    from datetime import datetime, timedelta
    from db.session import User
    r = db.register_user("__chat_token_frozen__", "test1234")
    if "error" in r:
        with db.session() as sess:
            uid = sess.query(User).filter_by(username="__chat_token_frozen__").first().id
    else:
        uid = r["id"]
    with db.session() as sess:
        u = sess.query(User).filter_by(id=uid).first()
        u.frozen_until = datetime.utcnow() + timedelta(days=3)
        u.freeze_reason = "测试冻结"
        sess.commit()
    dev_id = _mk_dev(db, user_id=uid)
    resp = client.post("/api/v1/agent/chat-token", headers=_h(dev_id))
    assert resp.status_code == 403
    assert "冻结" in resp.json()["detail"]
    # 清理：解冻，避免污染其它测试
    with db.session() as sess:
        u = sess.query(User).filter_by(id=uid).first()
        u.frozen_until = None
        sess.commit()
