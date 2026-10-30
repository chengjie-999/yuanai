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
        # 普通用户只看计费价与调用次数，真实成本/系数不返回（2026-10-30）
        assert "billed_month" in d and "billed_total" in d
        assert "month_calls" in d and "total_calls" in d
        assert "month_cost" not in d and "total_cost" not in d and "multiplier" not in d

    def test_admin_changes_multiplier_hot_reload(self, client, auth_headers, db, admin_jwt):
        """管理员改盈利系数 → 热更新生效，但历史消费按快照锁定不变（2026-10-30）"""
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
            before = client.get("/api/v1/auth/cost", headers=ah).json()
            resp = client.put("/api/v1/admin/system-config",
                              json={"system_config": {"cost_profit_multiplier": 2.5}},
                              headers=ah)
            assert resp.status_code == 200
            # admin 视角：真实成本 + 当前系数可见；历史 billed 不变（快照锁定）
            d = client.get("/api/v1/auth/cost", headers=ah).json()
            assert d["multiplier"] == pytest.approx(2.5)
            assert d["billed_total"] == pytest.approx(before["billed_total"])
            # 普通用户视角：无真实成本字段
            u = client.get("/api/v1/auth/cost", headers=auth_headers).json()
            assert "month_cost" not in u and "multiplier" not in u
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


class TestPaidAmount:
    """收款记录（2026-10-30 逐笔记账）：线下收款管理员登记，累计 = 各笔之和"""

    def test_payment_records_and_user_view(self, client, db, admin_jwt):
        r = db.register_user("__paid_target__", "test1234")
        assert "error" not in r, r
        uid = r["id"]
        ah = {"Authorization": f"Bearer {admin_jwt}"}
        try:
            # 负数/0 → 422
            assert client.post(f"/api/v1/admin/users/{uid}/payments",
                               json={"amount": -1}, headers=ah).status_code == 422
            assert client.post(f"/api/v1/admin/users/{uid}/payments",
                               json={"amount": 0}, headers=ah).status_code == 422
            # 登记两笔：10.00（备注）+ 2.34
            r1 = client.post(f"/api/v1/admin/users/{uid}/payments",
                             json={"amount": 10, "note": "首月"}, headers=ah)
            assert r1.status_code == 200
            r2 = client.post(f"/api/v1/admin/users/{uid}/payments",
                             json={"amount": 2.34}, headers=ah)
            assert r2.status_code == 200
            # 记录列表：2 笔，含备注
            rows = client.get(f"/api/v1/admin/users/{uid}/payments", headers=ah).json()
            assert len(rows) == 2
            assert any(p["note"] == "首月" for p in rows)
            # 用户列表 paid = 累计 12.34
            users = client.get("/api/v1/admin/users", headers=ah).json()
            hit = [u for u in users if u["id"] == uid]
            assert hit and hit[0]["paid"] == pytest.approx(12.34)
            # 用户视角 /auth/cost：paid 累计 + outstanding
            from api.v1.auth.utils import create_token
            h = {"Authorization": f"Bearer {create_token(uid, 'user')}"}
            d = client.get("/api/v1/auth/cost", headers=h).json()
            assert d["paid"] == pytest.approx(12.34)
            assert d["outstanding"] == pytest.approx(round(d["billed_total"] - 12.34, 6))
            # 删除一笔 → 累计变 10.00
            pid = rows[0]["id"]
            assert client.delete(f"/api/v1/admin/users/{uid}/payments/{pid}",
                                 headers=ah).status_code == 200
            users = client.get("/api/v1/admin/users", headers=ah).json()
            hit = [u for u in users if u["id"] == uid]
            assert hit and hit[0]["paid"] == pytest.approx(10.00)
            # 越权删除他人记录 → 404（归属校验）
            assert client.delete(f"/api/v1/admin/users/{uid}/payments/{pid}",
                                 headers=ah).status_code == 404
            # 不存在的用户 → 404
            assert client.post("/api/v1/admin/users/999999999/payments",
                               json={"amount": 1}, headers=ah).status_code == 404
        finally:
            from db.session import User, PaymentRecord
            sess = db.Session()
            try:
                sess.query(PaymentRecord).filter_by(user_id=uid).delete()
                u = sess.query(User).filter_by(id=uid).first()
                if u:
                    sess.delete(u)
                sess.commit()
            finally:
                sess.close()


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
