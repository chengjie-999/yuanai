"""R1' 邮箱验证码登录测试（2026-11-05）

覆盖：SMTP 未配置 503 / 邮箱格式 422 / 60s 冷却 429 / 每日上限 429 /
验证码错 5 次作废 / 一次性消费防重放 / 自动注册（协议强制留痕）/
存量用户登录 / 冻结拦截。
"""
import pytest

from api.v1.auth import email_code as ec


class _FakeRedis:
    """内存 Redis stub（set/get/delete/ttl/incr），测试注入"""

    def __init__(self):
        self.d = {}
        self.ttl_map = {}

    def set(self, k, v, ex=None):
        self.d[k] = str(v)
        if ex:
            self.ttl_map[k] = ex

    def get(self, k):
        return self.d.get(k)

    def delete(self, k):
        self.d.pop(k, None)

    def ttl(self, k):
        return self.ttl_map.get(k, 0)


@pytest.fixture()
def fake_rds(monkeypatch):
    rds = _FakeRedis()
    monkeypatch.setattr(ec, "_rds", lambda: rds)
    return rds


@pytest.fixture()
def smtp_ok(monkeypatch):
    monkeypatch.setattr(ec, "smtp_configured", lambda: True)
    monkeypatch.setattr(ec, "_send_email", lambda to, code: None)


def _mk_user_email():
    import secrets
    return f"__test_email_{secrets.token_hex(4)}@example.com"


@pytest.fixture()
def cleanup_users():
    """测试结束清理自动注册的用户"""
    created = []

    def _add(u):
        created.append(u)

    yield _add
    from db.session import get_db
    from db.session import User
    db = get_db()
    with db.session() as sess:
        for u in created:
            row = sess.query(User).filter_by(email=u).first()
            if row:
                sess.delete(row)
        sess.commit()


def _put_code(rds, email, code="123456"):
    rds.set(ec._CODE_KEY.format(email=email), code, ex=ec.CODE_TTL)
    rds.set(ec._TRY_KEY.format(email=email), 0, ex=ec.CODE_TTL)


# ---------------- 发送端点 ----------------

def test_send_code_503_when_smtp_unconfigured(client):
    resp = client.post("/api/v1/auth/email-code", json={"email": "a@example.com"})
    assert resp.status_code == 503


def test_send_code_invalid_email_422(client, smtp_ok):
    resp = client.post("/api/v1/auth/email-code", json={"email": "not-an-email"})
    assert resp.status_code == 422


def test_send_code_ok_and_cooldown(client, smtp_ok, fake_rds, monkeypatch):
    monkeypatch.setattr(ec, "consume_send_quota", lambda e, limit=10: True)
    email = _mk_user_email()
    resp = client.post("/api/v1/auth/email-code", json={"email": email})
    assert resp.status_code == 200
    assert resp.json().get("ok") is True
    # 冷却期内重发 → 429 且带剩余秒数
    resp2 = client.post("/api/v1/auth/email-code", json={"email": email})
    assert resp2.status_code == 429
    assert "秒" in resp2.json()["detail"]


def test_send_code_daily_limit_429(client, smtp_ok, fake_rds, monkeypatch):
    monkeypatch.setattr(ec, "consume_send_quota", lambda e, limit=10: False)
    resp = client.post("/api/v1/auth/email-code", json={"email": _mk_user_email()})
    assert resp.status_code == 429
    assert "上限" in resp.json()["detail"]


# ---------------- 验证码校验 ----------------

def test_verify_code_wrong_5_times_invalidates(fake_rds):
    email = _mk_user_email()
    _put_code(fake_rds, email, "654321")
    for _ in range(ec.MAX_TRY - 1):
        assert ec.verify_email_code(email, "000000") is False
    # 第 5 次错误 → 作废
    assert ec.verify_email_code(email, "000000") is False
    # 作废后正确码也失效
    assert ec.verify_email_code(email, "654321") is False


def test_verify_code_one_time_consumption(fake_rds):
    email = _mk_user_email()
    _put_code(fake_rds, email, "123456")
    assert ec.verify_email_code(email, "123456") is True
    # 一次性消费：防重放
    assert ec.verify_email_code(email, "123456") is False


def test_verify_code_expired(fake_rds):
    email = _mk_user_email()
    assert ec.verify_email_code(email, "123456") is False  # 无码


# ---------------- 登录（注册登录合一） ----------------

def test_email_login_requires_agreement_for_new_user(fake_rds, cleanup_users):
    email = _mk_user_email()
    _put_code(fake_rds, email, "123456")
    result = ec.email_login(email, "123456", agreement_accepted=False)
    assert "error" in result and result.get("agreement_required")
    cleanup_users(email)


def test_email_login_auto_register_and_relogin(fake_rds, cleanup_users):
    email = _mk_user_email()
    _put_code(fake_rds, email, "123456")
    result = ec.email_login(email, "123456", agreement_accepted=True)
    assert "error" not in result, result
    assert result["token"] and result["is_new"] is True
    cleanup_users(email)
    # 协议留痕：agreed_at 已写入
    from db.session import get_db
    from db.session import User
    with get_db().session() as sess:
        user = sess.query(User).filter_by(email=email).first()
        assert user is not None
        assert user.agreed_at is not None
        assert user.username.startswith("u_")
        assert user.display_name.startswith("小元用户_")
    # 再次登录：is_new=False，同一账号
    _put_code(fake_rds, email, "999999")
    result2 = ec.email_login(email, "999999")
    assert result2["is_new"] is False
    assert result2["user_id"] == result["user_id"]


def test_email_login_wrong_code(fake_rds):
    email = _mk_user_email()
    _put_code(fake_rds, email, "123456")
    result = ec.email_login(email, "000000")
    assert "error" in result and "验证码错误" in result["error"]


def test_email_login_frozen(fake_rds, cleanup_users):
    email = _mk_user_email()
    _put_code(fake_rds, email, "123456")
    result = ec.email_login(email, "123456", agreement_accepted=True)
    assert "error" not in result, result
    cleanup_users(email)
    # 冻结 → 403 语义（frozen 标记 + 原因）
    from datetime import datetime, timedelta
    from db.session import get_db
    from db.session import User
    with get_db().session() as sess:
        user = sess.query(User).filter_by(email=email).first()
        user.frozen_until = datetime.utcnow() + timedelta(days=3)
        sess.commit()
    _put_code(fake_rds, email, "888888")
    result2 = ec.email_login(email, "888888")
    assert "error" in result2 and result2.get("frozen") is True
    assert "冻结" in result2["error"]


# ---------------- 登录端点（公开路径 + 状态码） ----------------

def test_email_login_endpoint_flow(client, smtp_ok, fake_rds, cleanup_users, monkeypatch):
    monkeypatch.setattr(ec, "consume_send_quota", lambda e, limit=10: True)
    email = _mk_user_email()
    # 发码（端点写入 fake rds 里的真实 6 位码）
    resp = client.post("/api/v1/auth/email-code", json={"email": email})
    assert resp.status_code == 200
    cleanup_users(email)
    code = fake_rds.d[ec._CODE_KEY.format(email=email)]
    # 登录 → 自动注册 + token
    resp2 = client.post("/api/v1/auth/email-login",
                        json={"email": email, "code": code, "agreement_accepted": True})
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["token"] and data["is_new"] is True
    # 错误码 → 401
    resp3 = client.post("/api/v1/auth/email-login",
                        json={"email": email, "code": "000000", "agreement_accepted": True})
    assert resp3.status_code == 401
    # 未勾选协议（新邮箱）→ 422
    email2 = _mk_user_email()
    client.post("/api/v1/auth/email-code", json={"email": email2})
    cleanup_users(email2)
    code2 = fake_rds.d[ec._CODE_KEY.format(email=email2)]
    resp4 = client.post("/api/v1/auth/email-login",
                        json={"email": email2, "code": code2, "agreement_accepted": False})
    assert resp4.status_code == 422


if __name__ == "__main__":
    print("测试入口：pytest test/test_email_login.py -v")
