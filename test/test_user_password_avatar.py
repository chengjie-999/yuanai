"""设置/修改密码两态 + 头像上传测试（2026-11-06）

覆盖：邮箱注册用户无密码（password_hash 空串，密码登录拒绝）→ 设置密码后
可密码登录；有密码用户改密必须校验原密码；头像上传（真实图片校验/大小限制/
公开读取/越界 404）。
"""
import io
import secrets

import pytest

from db.session import get_db
from db.session import User


def _db_or_skip():
    try:
        return get_db()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


@pytest.fixture(scope="module")
def db():
    return _db_or_skip()


def _mk_email():
    return f"__pwav_{secrets.token_hex(4)}@example.com"


@pytest.fixture()
def email_user(db):
    """邮箱注册用户（password_hash 空串 = 无密码）"""
    email = _mk_email()
    with db.session() as sess:
        u = User(username=f"u_pwav_{secrets.token_hex(4)}", email=email,
                 password_hash="", display_name="测试邮箱用户",
                 role="user")
        sess.add(u)
        sess.commit()
        sess.refresh(u)
        uid = u.id
    yield {"id": uid, "email": email, "username": u.username}
    with db.session() as sess:
        u = sess.query(User).filter_by(id=uid).first()
        if u:
            sess.delete(u)
            sess.commit()


def _token_for(db, uid):
    from api.v1.auth.utils import create_token
    with db.session() as sess:
        u = sess.query(User).filter_by(id=uid).first()
    return create_token(uid, u.role or "user", u.username or "u")


# ---------------- 两态密码 ----------------

def test_email_user_cannot_password_login_before_set(db, email_user):
    """空 password_hash → 密码登录拒绝（无 ValueError 崩溃）"""
    assert db.authenticate_user(email_user["username"], "anything") is None


def test_email_user_set_password_then_login(client, db, email_user):
    """设置密码（old_password 空）→ 成功后可用密码登录"""
    h = {"Authorization": f"Bearer {_token_for(db, email_user['id'])}"}
    resp = client.put("/api/v1/auth/password",
                      json={"old_password": "", "new_password": "newpass123"}, headers=h)
    assert resp.status_code == 200, resp.text
    # 现在可以密码登录
    user = db.authenticate_user(email_user["username"], "newpass123")
    assert user is not None and user.id == email_user["id"]


def test_user_with_password_change_requires_old(client, db, email_user):
    h = {"Authorization": f"Bearer {_token_for(db, email_user['id'])}"}
    assert client.put("/api/v1/auth/password",
                      json={"old_password": "", "new_password": "first1234"}, headers=h).status_code == 200
    # 改密后 token_version+1 旧 token 全部失效（设计如此）——重签令牌继续
    h = {"Authorization": f"Bearer {_token_for(db, email_user['id'])}"}
    # 有密码后：旧密码错误 → 400；正确 → 200 且新密码生效
    r = client.put("/api/v1/auth/password",
                   json={"old_password": "wrongpwd", "new_password": "second123"}, headers=h)
    assert r.status_code == 400
    assert client.put("/api/v1/auth/password",
                      json={"old_password": "first1234", "new_password": "second123"}, headers=h).status_code == 200
    assert db.authenticate_user(email_user["username"], "second123") is not None
    assert db.authenticate_user(email_user["username"], "first1234") is None


def test_password_too_short_rejected(client, db, email_user):
    h = {"Authorization": f"Bearer {_token_for(db, email_user['id'])}"}
    r = client.put("/api/v1/auth/password", json={"old_password": "", "new_password": "short"}, headers=h)
    assert r.status_code == 422  # pydantic min_length=8


# ---------------- 头像上传 ----------------

def _png_bytes(color=(37, 99, 235), size=(64, 64)):
    from PIL import Image
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_avatar_upload_and_public_read(client, db, email_user):
    h = {"Authorization": f"Bearer {_token_for(db, email_user['id'])}"}
    resp = client.post("/api/v1/auth/avatar",
                       files={"avatar": ("a.png", _png_bytes(), "image/png")}, headers=h)
    assert resp.status_code == 200, resp.text
    avatar_url = resp.json()["avatar"]
    assert "/api/v1/auth/user-avatar/" in avatar_url
    # 公开读取（无需登录，URL 带版本参数按路径匹配）
    uid = email_user["id"]
    r2 = client.get(f"/api/v1/auth/user-avatar/{uid}")
    assert r2.status_code == 200
    assert r2.headers["content-type"].startswith("image/png")
    # 越界/不存在 uid → 404
    assert client.get("/api/v1/auth/user-avatar/0").status_code == 404
    assert client.get("/api/v1/auth/user-avatar/9999999999").status_code == 404


def test_avatar_rejects_fake_image(client, db, email_user):
    h = {"Authorization": f"Bearer {_token_for(db, email_user['id'])}"}
    resp = client.post("/api/v1/auth/avatar",
                       files={"avatar": ("x.png", b"not-an-image", "image/png")}, headers=h)
    assert resp.status_code == 400


def test_avatar_rejects_oversize(client, db, email_user):
    h = {"Authorization": f"Bearer {_token_for(db, email_user['id'])}"}
    big = b"\x00" * (2 * 1024 * 1024 + 1)
    resp = client.post("/api/v1/auth/avatar",
                       files={"avatar": ("big.png", big, "image/png")}, headers=h)
    assert resp.status_code == 400
    assert "过大" in resp.json()["detail"]


def test_avatar_requires_login(client):
    resp = client.post("/api/v1/auth/avatar",
                       files={"avatar": ("a.png", _png_bytes(), "image/png")})
    assert resp.status_code == 401


def test_check_returns_has_password_and_avatar(client, db, email_user):
    from api.v1.auth.utils import verify_token
    h = {"Authorization": f"Bearer {_token_for(db, email_user['id'])}"}
    r = client.post("/api/v1/auth/check", json={"token": _token_for(db, email_user["id"])}, headers=h)
    assert r.status_code == 200
    u = r.json()["user"]
    assert u["has_password"] is False
    assert u["avatar"] == ""


if __name__ == "__main__":
    print("测试入口：pytest test/test_user_password_avatar.py -v")
