"""
自服务安装码测试（2026-10-30）：普通用户自取安装码（生成即预绑定用户），
已绑定设备提示、重置生成新码并解绑旧设备、未登录 401。
"""
import pytest


def _db_or_skip():
    try:
        from db.session import get_db
        return get_db()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


@pytest.fixture(scope="module")
def db():
    return _db_or_skip()


@pytest.fixture(scope="module")
def code_user(db):
    r = db.register_user("__mycode_test__", "test1234")
    assert "error" not in r, r
    yield r["id"]
    from db.session import User, AgentDevice
    sess = db.Session()
    try:
        sess.query(AgentDevice).filter_by(user_id=r["id"]).delete()
        u = sess.query(User).filter_by(id=r["id"]).first()
        if u:
            sess.delete(u)
        sess.commit()
    finally:
        sess.close()


class TestMyAgentCode:
    def test_get_code_persists_and_prebinds(self, client, db, code_user):
        from api.v1.auth.utils import create_token
        h = {"Authorization": f"Bearer {create_token(code_user, 'user')}"}
        # 未登录 → 401
        assert client.get("/api/v1/agent/my-code").status_code == 401
        # 首次取码 → 生成 + 预绑定 user_id
        resp = client.get("/api/v1/agent/my-code", headers=h)
        assert resp.status_code == 200
        d = resp.json()
        assert d["code"].startswith("YUAN-") and d["bound"] is False
        # 再次取 → 复用同一未用码（不重复生成）
        resp2 = client.get("/api/v1/agent/my-code", headers=h)
        assert resp2.json()["code"] == d["code"]
        # 预绑定落库
        from db.session import AgentDevice
        sess = db.Session()
        try:
            dev = sess.query(AgentDevice).filter_by(install_code=d["code"]).first()
            assert dev and dev.user_id == code_user and dev.agent_secret == ""
        finally:
            sess.close()

    def test_bound_device_issues_code_for_more_devices(self, client, db, code_user):
        """N1（2026-11-06）一账号多设备：已绑 1 台 → 仍发新码（换电脑零迁移）"""
        from api.v1.auth.utils import create_token
        from db.session import AgentDevice
        import uuid as _uuid
        code = "YUAN-" + str(_uuid.uuid4())[:12].upper()  # 每次运行唯一（防脏数据撞唯一索引）
        sess = db.Session()
        try:
            sess.add(AgentDevice(install_code=code,
                                 agent_secret="sec", machine_name="测试电脑",
                                 user_id=code_user))
            sess.commit()
        finally:
            sess.close()
        h = {"Authorization": f"Bearer {create_token(code_user, 'user')}"}
        d = client.get("/api/v1/agent/my-code", headers=h).json()
        assert d["bound"] is False and d["code"].startswith("YUAN-")
        assert d["device_count"] == 1

    def test_reset_code_unbinds_old(self, client, db, code_user):
        from api.v1.auth.utils import create_token
        h = {"Authorization": f"Bearer {create_token(code_user, 'user')}"}
        resp = client.post("/api/v1/agent/my-code", headers=h)
        assert resp.status_code == 200
        d = resp.json()
        assert d["code"].startswith("YUAN-")
        # 旧设备（含已绑定）全部解绑，新码预绑定
        from db.session import AgentDevice
        sess = db.Session()
        try:
            devices = sess.query(AgentDevice).filter_by(user_id=code_user).all()
            assert len(devices) == 1  # 只剩新码一行
            assert devices[0].install_code == d["code"]
        finally:
            sess.close()
