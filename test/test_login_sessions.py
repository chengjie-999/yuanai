"""
并发登录数限制测试（2026-10-30 用户拍板：单账号最多 5 台设备，超限踢最旧会话）

机制：登录签发带 sess 标记的 JWT → Redis hash login_sessions:{uid} 登记
（jti→exp）；第 6 台登录踢掉 exp 最小（最早登录）的 jti，被踢设备下个请求 401。
桥接/长令牌（create_token 无 sess 标记）不受影响；Redis 故障 fail-open。
"""
import time

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
def sess_user(db):
    """专用测试账号（不污染 __test_api_user__ 的真实会话）"""
    r = db.register_user("__sess_limit__", "test1234")
    assert "error" not in r, r
    yield r["id"]
    from db.session import User
    sess = db.Session()
    try:
        u = sess.query(User).filter_by(id=r["id"]).first()
        if u:
            sess.delete(u)
            sess.commit()
    finally:
        sess.close()


def _login_tokens(client, count: int) -> list:
    tokens = []
    for _ in range(count):
        resp = client.post("/api/v1/auth/login", json={
            "username": "__sess_limit__", "password": "test1234"})
        assert resp.status_code == 200
        tokens.append(resp.json()["token"])
        time.sleep(0.05)  # 错开登记顺序（exp 相同，踢最旧按 hash 序仍有确定性）
    return tokens


def _cost_with(t: str, client) -> int:
    return client.get("/api/v1/auth/cost",
                      headers={"Authorization": f"Bearer {t}"}).status_code


class TestLoginSessionLimit:
    def test_five_devices_all_valid_sixth_kicks_oldest(self, client, db, sess_user):
        try:
            tokens = _login_tokens(client, 5)
            # 5 台全部可用
            assert all(_cost_with(t, client) == 200 for t in tokens)
            # 第 6 台登录
            sixth = _login_tokens(client, 1)[0]
            # 最旧一台（tokens[0]）被踢：401 且带下线提示；其余 4 台 + 新会话有效
            r = client.get("/api/v1/auth/cost",
                           headers={"Authorization": f"Bearer {tokens[0]}"})
            assert r.status_code == 401
            assert "下线" in r.json()["detail"]
            assert all(_cost_with(t, client) == 200 for t in tokens[1:])
            assert _cost_with(sixth, client) == 200
            # 被踢用户可重新登录（新会话挤掉 tokens[1]）
            seventh = _login_tokens(client, 1)[0]
            assert _cost_with(seventh, client) == 200
            assert _cost_with(tokens[1], client) == 401
        finally:
            try:
                from db.redis_client import get_redis
                get_redis().delete(f"login_sessions:{sess_user}")
            except Exception:
                pass

    def test_bridge_token_exempt(self, client, db, sess_user):
        """桥接/长令牌（无 sess 标记）不参与会话数校验，即使清单里没有它的 jti"""
        try:
            tokens = _login_tokens(client, 1)  # 建立会话清单
            assert _cost_with(tokens[0], client) == 200
            from api.v1.auth.utils import create_token
            bridge = create_token(sess_user, "user", "__sess_limit__")
            assert _cost_with(bridge, client) == 200  # 清单存在但无此 jti → 仍放行
        finally:
            try:
                from db.redis_client import get_redis
                get_redis().delete(f"login_sessions:{sess_user}")
            except Exception:
                pass

    def test_redis_fail_open(self, client, db, sess_user, monkeypatch):
        """Redis 故障：登录与请求都放行（不限流降级，不影响可用性）"""
        tokens = _login_tokens(client, 1)
        try:
            def _boom(*a, **k):
                raise RuntimeError("redis down")
            monkeypatch.setattr("db.redis_client.get_redis", _boom)
            # 清单读取失败 → fail-open 放行
            assert _cost_with(tokens[0], client) == 200
            # 登记失败静默，登录本身成功
            resp = client.post("/api/v1/auth/login", json={
                "username": "__sess_limit__", "password": "test1234"})
            assert resp.status_code == 200
        finally:
            try:
                from db.redis_client import get_redis
                get_redis().delete(f"login_sessions:{sess_user}")
            except Exception:
                pass
