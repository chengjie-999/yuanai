"""
欠费限制测试（2026-10-30 用户拍板）：显示金额（收款 − 系数成本）≤ -ARREARS_LIMIT
（默认 20 元）时限制聊天使用并提示缴费；admin 豁免；异常静默放行。
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


class TestArrearsHelper:
    def test_helper_blocks_when_owed(self, db, monkeypatch):
        """欠费满门槛 → 返回提示文案（含欠费金额与「已限制使用」）"""
        from api.v1.chat.router import _check_arrears
        from db.session import TokenUsage
        monkeypatch.setattr("config.settings.ARREARS_LIMIT", 0.001)  # 测试门槛降到 0.001
        r = db.register_user("__arrears_test__", "test1234")
        assert "error" not in r, r
        uid = r["id"]
        try:
            sess = db.Session()
            try:
                sess.add(TokenUsage(user_id=uid, model="deepseek-flash",
                                    prompt_tokens=100000, completion_tokens=0,
                                    total_tokens=100000))
                sess.commit()
            finally:
                sess.close()
            msg = _check_arrears(uid)
            assert msg and "欠费" in msg and "已限制使用" in msg
        finally:
            from db.session import User
            sess = db.Session()
            try:
                sess.query(TokenUsage).filter_by(user_id=uid).delete()
                u = sess.query(User).filter_by(id=uid).first()
                if u:
                    sess.delete(u)
                sess.commit()
            finally:
                sess.close()

    def test_helper_passes_when_clean(self, db, monkeypatch):
        """无欠费（无用量且无收款）→ None 放行"""
        from api.v1.chat.router import _check_arrears
        monkeypatch.setattr("config.settings.ARREARS_LIMIT", 0.001)
        r = db.register_user("__arrears_clean__", "test1234")
        assert "error" not in r, r
        uid = r["id"]
        try:
            assert _check_arrears(uid) is None
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

    def test_helper_passes_when_paid_up(self, db, monkeypatch):
        """收款 ≥ 系数成本 → 不欠费放行"""
        from api.v1.chat.router import _check_arrears
        from db.session import TokenUsage
        monkeypatch.setattr("config.settings.ARREARS_LIMIT", 0.001)
        r = db.register_user("__arrears_paid__", "test1234")
        assert "error" not in r, r
        uid = r["id"]
        try:
            sess = db.Session()
            try:
                sess.add(TokenUsage(user_id=uid, model="deepseek-flash",
                                    prompt_tokens=100000, completion_tokens=0,
                                    total_tokens=100000))
                sess.commit()
            finally:
                sess.close()
            db.add_payment(uid, 999.0, "足额")  # 收款远大于系数成本
            assert _check_arrears(uid) is None
        finally:
            from db.session import User, PaymentRecord
            sess = db.Session()
            try:
                sess.query(TokenUsage).filter_by(user_id=uid).delete()
                sess.query(PaymentRecord).filter_by(user_id=uid).delete()
                u = sess.query(User).filter_by(id=uid).first()
                if u:
                    sess.delete(u)
                sess.commit()
            finally:
                sess.close()


class TestArrearsEndpoint:
    def test_stream_403_when_arrears(self, client, db, monkeypatch):
        """欠费用户发消息 → 403 + 提示（在 LLM 调用前拦截）"""
        from db.session import TokenUsage
        monkeypatch.setattr("config.settings.ARREARS_LIMIT", 0.001)
        r = db.register_user("__arrears_api__", "test1234")
        assert "error" not in r, r
        uid = r["id"]
        try:
            sess = db.Session()
            try:
                sess.add(TokenUsage(user_id=uid, model="deepseek-flash",
                                    prompt_tokens=100000, completion_tokens=0,
                                    total_tokens=100000))
                sess.commit()
            finally:
                sess.close()
            from api.v1.auth.utils import create_token
            h = {"Authorization": f"Bearer {create_token(uid, 'user')}"}
            resp = client.post("/api/v1/chat/stream",
                               json={"prompt": "你好"}, headers=h)
            assert resp.status_code == 403
            assert "欠费" in resp.json()["detail"]
        finally:
            from db.session import User
            sess = db.Session()
            try:
                sess.query(TokenUsage).filter_by(user_id=uid).delete()
                u = sess.query(User).filter_by(id=uid).first()
                if u:
                    sess.delete(u)
                sess.commit()
            finally:
                sess.close()
