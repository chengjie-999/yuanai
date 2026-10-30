"""
后台用户管理端点测试：重置密码（2026-10-30）
密码 bcrypt 单向哈希无法显示——忘记密码的账号由管理员重置；
重置后 token_version+1 旧会话全失效。
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
def admin_jwt(db):
    from db.session import User
    from api.v1.auth.utils import create_token
    sess = db.Session()
    try:
        old = sess.query(User).filter_by(username="__reset_admin__").first()
        if old:
            sess.delete(old)
            sess.commit()
    finally:
        sess.close()
    r = db.register_user("__reset_admin__", "test1234", role="admin")
    assert "error" not in r, r
    yield create_token(r["id"], "admin")
    sess = db.Session()
    try:
        u = sess.query(User).filter_by(id=r["id"]).first()
        if u:
            sess.delete(u)
            sess.commit()
    finally:
        sess.close()


class TestPasswordValidation:
    """创建/改密与登录校验同口径（2026-10-30 修复：口径不一致会造出永远登不上的账号）"""

    def test_admin_create_rejects_short_password(self, client, admin_jwt):
        ah = {"Authorization": f"Bearer {admin_jwt}"}
        resp = client.post("/api/v1/admin/users/create",
                           json={"username": "shortpwtest", "password": "short"},
                           headers=ah)
        assert resp.status_code == 422

    def test_admin_create_rejects_short_username(self, client, admin_jwt):
        ah = {"Authorization": f"Bearer {admin_jwt}"}
        resp = client.post("/api/v1/admin/users/create",
                           json={"username": "ab", "password": "longpass123"},
                           headers=ah)
        assert resp.status_code == 422

    def test_change_password_rejects_short_new(self, client, db, admin_jwt):
        r = db.register_user("__pwchange_target__", "oldpass123")
        assert "error" not in r, r
        uid = r["id"]
        try:
            from api.v1.auth.utils import create_token
            h = {"Authorization": f"Bearer {create_token(uid, 'user')}"}
            resp = client.put("/api/v1/auth/password",
                              json={"old_password": "oldpass123", "new_password": "short"},
                              headers=h)
            assert resp.status_code == 422
        finally:
            from db.session import User
            sess = db.Session()
            try:
                u = sess.query(User).filter_by(id=uid).first()
                if u:
                    sess.delete(u)
                    sess.commit()
            finally:
                sess.close()


class TestUserCost:
    """用户本人成本端点（2026-10-30）：计费价 = 真实成本 × 盈利系数"""

    def test_my_cost_shape_and_auth(self, client, auth_headers):
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        # 未登录 → 401
        assert client.get("/api/v1/auth/cost").status_code == 401
        resp = client.get("/api/v1/auth/cost", headers=auth_headers)
        assert resp.status_code == 200
        d = resp.json()
        assert d["multiplier"] == pytest.approx(1.8)
        assert d["billed_month"] == round(d["month_cost"] * d["multiplier"], 2)
        assert d["billed_total"] == round(d["total_cost"] * d["multiplier"], 2)
        assert "month_calls" in d and "total_calls" in d

    def test_admin_changes_multiplier_hot_reload(self, client, auth_headers, db, admin_jwt):
        """管理员改盈利系数 → 热更新 → /auth/cost 立即反映（2026-10-30）"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        import os as _os
        _path = "data/models.json"
        backup = None
        if _os.path.exists(_path):
            with open(_path, "r", encoding="utf-8") as f:
                backup = f.read()
        ah = {"Authorization": f"Bearer {admin_jwt}"}
        try:
            resp = client.put("/api/v1/admin/system-config",
                              json={"system_config": {"cost_profit_multiplier": 2.5}},
                              headers=ah)
            assert resp.status_code == 200
            d = client.get("/api/v1/auth/cost", headers=auth_headers).json()
            assert d["multiplier"] == pytest.approx(2.5)
            assert d["billed_month"] == round(d["month_cost"] * 2.5, 2)
            # 非法值 → 400（小于下限）
            resp = client.put("/api/v1/admin/system-config",
                              json={"system_config": {"cost_profit_multiplier": 0.01}},
                              headers=ah)
            assert resp.status_code == 400
        finally:
            import config.settings as _s
            if backup is None:
                if _os.path.exists(_path):
                    _os.remove(_path)
            else:
                with open(_path, "w", encoding="utf-8") as f:
                    f.write(backup)
            _s.reload_system_config()


class TestResetPassword:
    def test_reset_password_flow(self, client, db, admin_jwt):
        """重置 → 新密码可登录、旧密码 401；非 admin 403；管理员密码不可重置"""
        r = db.register_user("__reset_target__", "oldpass123")
        assert "error" not in r, r
        uid = r["id"]
        ah = {"Authorization": f"Bearer {admin_jwt}"}
        try:
            # 普通用户调用 → 403
            from db.session import User
            from api.v1.auth.utils import create_token
            target_token = create_token(uid, "user")
            resp = client.post(f"/api/v1/admin/users/{uid}/reset-password",
                               json={"password": "hackpass123"},
                               headers={"Authorization": f"Bearer {target_token}"})
            assert resp.status_code == 403
            # 密码太短 → 422
            resp = client.post(f"/api/v1/admin/users/{uid}/reset-password",
                               json={"password": "short"}, headers=ah)
            assert resp.status_code == 422
            # 管理员重置 → 200
            resp = client.post(f"/api/v1/admin/users/{uid}/reset-password",
                               json={"password": "newpass456"}, headers=ah)
            assert resp.status_code == 200
            # 旧密码登录失败
            resp = client.post("/api/v1/auth/login", json={
                "username": "__reset_target__", "password": "oldpass123"})
            assert resp.status_code == 401
            # 新密码登录成功
            resp = client.post("/api/v1/auth/login", json={
                "username": "__reset_target__", "password": "newpass456"})
            assert resp.status_code == 200
            # 不存在的用户 → 404
            assert client.post("/api/v1/admin/users/999999999/reset-password",
                               json={"password": "whatever123"}, headers=ah).status_code == 404
        finally:
            sess = db.Session()
            try:
                u = sess.query(User).filter_by(id=uid).first()
                if u:
                    sess.delete(u)
                    sess.commit()
            finally:
                sess.close()
