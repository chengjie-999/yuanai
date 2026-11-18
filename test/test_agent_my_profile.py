"""本机账号归属端点测试（2026-11-08）：设备凭据鉴权 → 绑定用户信息。

托盘菜单「账号」项消费；零网络——_verify_agent_secret mock，DB 直查。"""

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


def test_my_profile_requires_creds(client):
    assert client.get("/api/v1/agent/my-profile").status_code == 401


def test_my_profile_bound(client, authed, db):
    """已绑定设备 → 返回用户名/昵称/机器名"""
    from db.session import User
    r = db.register_user("__profile_user__", "test1234")
    if "error" in r:
        with db.session() as sess:
            uid = sess.query(User).filter_by(username="__profile_user__").first().id
    else:
        uid = r["id"]
    dev_id = _mk_dev(db, user_id=uid)
    resp = client.get("/api/v1/agent/my-profile", headers=_h(dev_id))
    assert resp.status_code == 200
    d = resp.json()
    assert d["bound"] is True
    assert d["user"]["username"] == "__profile_user__"
    assert d["machine_name"] == "我的电脑"


def test_my_profile_unbound(client, authed, db):
    """未绑定设备 → bound=False、user=None（不 403，托盘显示未绑定）"""
    dev_id = _mk_dev(db, user_id=None)
    resp = client.get("/api/v1/agent/my-profile", headers=_h(dev_id))
    assert resp.status_code == 200
    d = resp.json()
    assert d["bound"] is False
    assert d["user"] is None


# ---------- T2 终端主题（2026-11-18）：my-theme 端点 ----------

def test_my_theme_requires_creds(client):
    assert client.get("/api/v1/agent/my-theme").status_code == 401
    assert client.put("/api/v1/agent/my-theme",
                      json={"theme": "dark"}).status_code == 401


def test_my_theme_unbound_403(client, authed, db):
    """未绑定设备 → 403（主题是用户数据，与记忆/计划同口径）"""
    dev_id = _mk_dev(db, user_id=None)
    resp = client.get("/api/v1/agent/my-theme", headers=_h(dev_id))
    assert resp.status_code == 403


def test_my_theme_roundtrip(client, authed, db):
    """已绑定设备：默认空 → PUT dark → GET dark；非法值 400"""
    from db.session import User
    r = db.register_user("__theme_user__", "test1234")
    if "error" in r:
        with db.session() as sess:
            uid = sess.query(User).filter_by(username="__theme_user__").first().id
    else:
        uid = r["id"]
    dev_id = _mk_dev(db, user_id=uid)
    h = _h(dev_id)
    db.update_user_theme(uid, "")  # 幂等：重置前轮残留（同用户跨轮复用）
    resp = client.get("/api/v1/agent/my-theme", headers=h)
    assert resp.status_code == 200
    assert resp.json()["theme"] == ""  # 默认未设置

    resp = client.put("/api/v1/agent/my-theme", json={"theme": "dark"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["theme"] == "dark"

    resp = client.get("/api/v1/agent/my-theme", headers=h)
    assert resp.json()["theme"] == "dark"

    # 与网站 /auth/theme 同列互同步（用户 JWT 视角读到终端写的值）
    assert client.put("/api/v1/agent/my-theme",
                      json={"theme": "pink"}, headers=h).status_code == 400
