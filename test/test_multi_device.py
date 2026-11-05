"""N1 一账号多设备测试（2026-11-06）

覆盖：绑定不再一对一（第二台可绑/设备数上限 400/他人设备仍 400）；
my-code 多设备再取码与上限 bound；桥接选设备在线优先。
"""
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


def _mk_dev(db, user_id=None, secret="", enabled=1):
    from db.session import AgentDevice
    with db.session() as sess:
        dev = AgentDevice(install_code="YUAN-" + "-".join(secrets.token_hex(2).upper() for _ in range(3)),
                          agent_secret=secret, user_id=user_id, enabled=enabled)
        sess.add(dev)
        sess.commit()
        return dev.id


def _cleanup(db, ids):
    from db.session import AgentDevice
    with db.session() as sess:
        for i in ids:
            dev = sess.query(AgentDevice).filter_by(id=i).first()
            if dev:
                sess.delete(dev)
        sess.commit()


def _admin_jwt(db):
    from db.session import User
    from api.v1.auth.utils import create_token
    with db.session() as sess:
        u = sess.query(User).filter_by(username="__n1_admin__").first()
        if u is None:
            r = db.register_user("__n1_admin__", "test1234", role="admin")
            u = sess.query(User).filter_by(id=r["id"]).first()
    return create_token(u.id, "admin"), u.id


def _user_jwt(db):
    from db.session import User
    from api.v1.auth.utils import create_token
    with db.session() as sess:
        u = sess.query(User).filter_by(username="__n1_user__").first()
        if u is None:
            r = db.register_user("__n1_user__", "test1234")
            u = sess.query(User).filter_by(id=r["id"]).first()
    return create_token(u.id, "user"), u.id


# ---------------- 绑定多设备 ----------------

def test_bind_second_device_allowed(client, db):
    """N1：同一用户可绑第二台设备（一对一限制移除）"""
    from db.session import AgentDevice
    uid = _user_jwt(db)[1]
    dev1, dev2 = _mk_dev(db), _mk_dev(db)
    try:
        ah = {"Authorization": f"Bearer {_admin_jwt(db)[0]}"}
        r1 = client.post("/api/v1/admin/agent-bind", json={"agent_id": dev1, "user_id": uid}, headers=ah)
        assert r1.status_code == 200, r1.text
        r2 = client.post("/api/v1/admin/agent-bind", json={"agent_id": dev2, "user_id": uid}, headers=ah)
        assert r2.status_code == 200, r2.text
    finally:
        _cleanup(db, [dev1, dev2])


def test_bind_respects_other_owner(client, db):
    """他人已绑设备仍拒绝"""
    uid_a = _user_jwt(db)[1]
    uid_b = _admin_jwt(db)[1]
    dev = _mk_dev(db, user_id=uid_b)
    try:
        ah = {"Authorization": f"Bearer {_admin_jwt(db)[0]}"}
        r = client.post("/api/v1/admin/agent-bind", json={"agent_id": dev, "user_id": uid_a}, headers=ah)
        assert r.status_code == 400
        assert "已绑定" in r.json()["detail"]
    finally:
        _cleanup(db, [dev])


def test_bind_device_limit(client, db, monkeypatch):
    """设备数达上限 → 400"""
    monkeypatch.setattr("config.settings.AGENT_MAX_DEVICES_PER_USER", 1)
    uid = _user_jwt(db)[1]
    dev1, dev2 = _mk_dev(db, user_id=uid, secret="s1"), _mk_dev(db)
    try:
        ah = {"Authorization": f"Bearer {_admin_jwt(db)[0]}"}
        r = client.post("/api/v1/admin/agent-bind", json={"agent_id": dev2, "user_id": uid}, headers=ah)
        assert r.status_code == 400
        assert "上限" in r.json()["detail"]
    finally:
        _cleanup(db, [dev1, dev2])


# ---------------- my-code 多设备 ----------------

def test_my_code_issues_code_after_bound(client, db):
    """已绑 1 台 → 仍可取新码（换电脑零迁移）"""
    uid = _user_jwt(db)[1]
    dev = _mk_dev(db, user_id=uid, secret="bound-secret")
    try:
        h = {"Authorization": f"Bearer {_user_jwt(db)[0]}"}
        r = client.get("/api/v1/agent/my-code", headers=h)
        data = r.json()
        assert data["code"].startswith("YUAN-")
        assert data["bound"] is False
        assert data["device_count"] == 1
        assert data["max_devices"] >= 1
    finally:
        _cleanup(db, [dev])


def test_my_code_bound_at_limit(client, db, monkeypatch):
    """达上限 → bound=True 无码"""
    uid = _user_jwt(db)[1]
    dev = _mk_dev(db, user_id=uid, secret="s")
    try:
        # 清掉历史 pending 码（前面测试可能留），只留已注册设备
        from db.session import AgentDevice
        with db.session() as sess:
            for d in sess.query(AgentDevice).filter(AgentDevice.user_id == uid,
                                                    AgentDevice.agent_secret == "").all():
                sess.delete(d)
            sess.commit()
        h = {"Authorization": f"Bearer {_user_jwt(db)[0]}"}
        monkeypatch.setattr("config.settings.AGENT_MAX_DEVICES_PER_USER", 1)
        r = client.get("/api/v1/agent/my-code", headers=h)
        data = r.json()
        assert data["bound"] is True and data["code"] == ""
    finally:
        _cleanup(db, [dev])


# ---------------- 桥接选设备 ----------------

def test_get_bound_agent_prefers_online(db, monkeypatch):
    """多设备：在线优先"""
    from api.v1.agent import router as ar
    uid = _user_jwt(db)[1]
    dev_off, dev_on = _mk_dev(db, user_id=uid, secret="a"), _mk_dev(db, user_id=uid, secret="b")
    try:
        ar._agents[str(dev_on)] = _FakeWS()
        monkeypatch.setattr(ar, "_bind_cache", {})
        assert ar._get_bound_agent_id(uid) == str(dev_on)
    finally:
        ar._agents.pop(str(dev_on), None)
        monkeypatch.setattr(ar, "_bind_cache", {})
        _cleanup(db, [dev_off, dev_on])


class _FakeWS:
    client_state = type("S", (), {"name": "CONNECTED"})()


def test_get_bound_agent_latest_active_when_all_offline(db, monkeypatch):
    """全离线：选最近活跃"""
    from datetime import datetime, timedelta
    from api.v1.agent import router as ar
    from db.session import AgentDevice
    uid = _user_jwt(db)[1]
    dev_old, dev_new = _mk_dev(db, user_id=uid, secret="x"), _mk_dev(db, user_id=uid, secret="y")
    try:
        with db.session() as sess:
            d1 = sess.query(AgentDevice).filter_by(id=dev_old).first()
            d1.last_seen = datetime.utcnow() - timedelta(days=2)
            d2 = sess.query(AgentDevice).filter_by(id=dev_new).first()
            d2.last_seen = datetime.utcnow()
            sess.commit()
        monkeypatch.setattr(ar, "_bind_cache", {})
        assert ar._get_bound_agent_id(uid) == str(dev_new)
    finally:
        monkeypatch.setattr(ar, "_bind_cache", {})
        _cleanup(db, [dev_old, dev_new])


if __name__ == "__main__":
    print("测试入口：pytest test/test_multi_device.py -v")
