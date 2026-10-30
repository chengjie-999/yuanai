"""
注册开放与优化测试（2026-10-30 用户拍板：默认开放 + 用户名唯一/合规 + 防刷）

覆盖：默认开关、协议后端强制、admin 词/违规词拦截、重复用户名 400、
IntegrityError 兜底（db 层）、注册后 agreed_at 留痕 + 可登录、每 IP 每日 3 账号限流。
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


@pytest.fixture(autouse=True)
def _clear_register_quota():
    """每测清注册配额键（本文件多测试共享同一 IP 计数，否则顺序敏感）"""
    try:
        from db.redis_client import get_redis
        from datetime import datetime
        get_redis().delete(f"quota:register:testclient:{datetime.now().strftime('%Y%m%d')}")
    except Exception:
        pass
    yield


def _cleanup(db, username: str):
    from db.session import User
    sess = db.Session()
    try:
        u = sess.query(User).filter_by(username=username).first()
        if u:
            sess.delete(u)
            sess.commit()
    finally:
        sess.close()


class TestRegisterOpen:
    def test_register_open_default_true(self):
        import config.settings as s
        assert s.REGISTER_OPEN is True  # 2026-10-30 开放：默认开（后台开关可关）


class TestRegisterValidation:
    def test_agreement_required(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "__reg_noagree__", "password": "test1234"})
        assert resp.status_code == 422  # 后端强制协议勾选

    def test_admin_word_blocked(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "admin001", "password": "test1234", "agreement_accepted": True})
        assert resp.status_code == 400
        assert "admin" in resp.json()["detail"]

    def test_unsafe_word_blocked(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "恐怖袭击助手", "password": "test1234", "agreement_accepted": True})
        assert resp.status_code == 400

    def test_duplicate_username_400(self, client, db):
        r = db.register_user("__reg_dup__", "test1234")
        assert "error" not in r, r
        try:
            resp = client.post("/api/v1/auth/register", json={
                "username": "__reg_dup__", "password": "test1234", "agreement_accepted": True})
            assert resp.status_code == 400
            assert "已存在" in resp.json()["detail"]
        finally:
            _cleanup(db, "__reg_dup__")

    def test_db_layer_duplicate_returns_error(self, db):
        """db.register_user 幂等友好：重复用户名返回 error 而非抛异常"""
        r1 = db.register_user("__reg_dbdup__", "test1234")
        assert "error" not in r1, r1
        try:
            r2 = db.register_user("__reg_dbdup__", "test1234")
            assert "error" in r2 and "已存在" in r2["error"]
        finally:
            _cleanup(db, "__reg_dbdup__")


class TestRegisterFlow:
    def test_register_then_login(self, client, db):
        """注册成功 → agreed_at 已留痕 → 新账号可登录"""
        try:
            from db.redis_client import get_redis
            from datetime import datetime
            get_redis().delete(f"quota:register:testclient:{datetime.now().strftime('%Y%m%d')}")
        except Exception:
            pass
        resp = client.post("/api/v1/auth/register", json={
            "username": "__reg_flow__", "password": "test1234",
            "display_name": "流程测试", "agreement_accepted": True})
        assert resp.status_code == 200
        try:
            from db.session import User
            sess = db.Session()
            try:
                u = sess.query(User).filter_by(username="__reg_flow__").first()
                assert u and u.agreed_at is not None  # 协议留痕
                assert u.display_name == "流程测试"
            finally:
                sess.close()
            login = client.post("/api/v1/auth/login", json={
                "username": "__reg_flow__", "password": "test1234"})
            assert login.status_code == 200
            assert login.json()["token"]
        finally:
            _cleanup(db, "__reg_flow__")

    def test_register_rate_limit_per_ip(self, client, db):
        """每 IP 每日 3 账号：第 4 次注册 429"""
        try:
            from db.redis_client import get_redis
            from datetime import datetime
            get_redis().delete(f"quota:register:testclient:{datetime.now().strftime('%Y%m%d')}")
        except Exception:
            pass
        created = []
        for i in range(3):
            resp = client.post("/api/v1/auth/register", json={
                "username": f"__reg_rl_{i}__", "password": "test1234",
                "agreement_accepted": True})
            assert resp.status_code == 200, f"第 {i+1} 个应成功: {resp.text}"
            created.append(f"__reg_rl_{i}__")
        resp = client.post("/api/v1/auth/register", json={
            "username": "__reg_rl_3__", "password": "test1234",
            "agreement_accepted": True})
        assert resp.status_code == 429
        for name in created:
            _cleanup(db, name)
