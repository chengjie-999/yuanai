"""SMTP 后台热配置测试（R1'，2026-11-05）

覆盖：admin 鉴权 / PUT-GET 往返（密码脱敏永不回传）/ 空密码保持原值 /
选择链 env 优先 → 后台配置 / 未配置 503 / 测试发送护栏（422/503/冷却/成功）/
ENCRYPTION_PASSWORD 存在时授权码加密落盘。
"""
import json
import os

import pytest

from api.v1.models_file import _MODELS_PATH


# ---------------- fixtures ----------------

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
        old = sess.query(User).filter_by(username="__smtp_admin__").first()
        if old:
            sess.delete(old)
            sess.commit()
    finally:
        sess.close()
    r = db.register_user("__smtp_admin__", "test1234", role="admin")
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


@pytest.fixture()
def models_file_backup():
    """备份/恢复 data/models.json（与 test_agent_models_api 同套路）"""
    backup = None
    if os.path.exists(_MODELS_PATH):
        with open(_MODELS_PATH, "r", encoding="utf-8") as f:
            backup = f.read()
    yield
    if backup is None:
        if os.path.exists(_MODELS_PATH):
            os.remove(_MODELS_PATH)
    else:
        with open(_MODELS_PATH, "w", encoding="utf-8") as f:
            f.write(backup)


@pytest.fixture()
def no_env_smtp(monkeypatch):
    """清空 env 侧 SMTP（避免本地 .env 干扰后台配置选择链测试）"""
    import config.settings as s
    monkeypatch.setattr(s, "SMTP_HOST", "")
    monkeypatch.setattr(s, "SMTP_USER", "")
    monkeypatch.setattr(s, "SMTP_PASSWORD", "")
    monkeypatch.setattr(s, "SMTP_FROM", "")


def _put_smtp(client, jwt, payload):
    return client.put("/api/v1/admin/smtp-config",
                      json=payload, headers={"Authorization": f"Bearer {jwt}"})


def _get_smtp(client, jwt=None):
    h = {"Authorization": f"Bearer {jwt}"} if jwt else {}
    return client.get("/api/v1/admin/smtp-config", headers=h)


# ---------------- 鉴权 ----------------

def test_smtp_endpoints_require_admin(client):
    assert _get_smtp(client).status_code in (401, 403)
    assert client.put("/api/v1/admin/smtp-config", json={"host": "x", "user": "y"}).status_code in (401, 403)
    assert client.post("/api/v1/admin/smtp-config/test", json={"email": "a@b.com"}).status_code in (401, 403)


# ---------------- PUT/GET 往返 + 密码脱敏 ----------------

def test_smtp_roundtrip_password_masked(client, admin_jwt, models_file_backup, no_env_smtp):
    h = {"Authorization": f"Bearer {admin_jwt}"}
    resp = client.put("/api/v1/admin/smtp-config", json={
        "host": "smtp.163.com", "port": 465, "user": "sender@163.com",
        "password": "SA1234567890", "from_addr": "小元AI <sender@163.com>", "use_ssl": True,
    }, headers=h)
    assert resp.status_code == 200, resp.text
    st = resp.json()["status"]
    assert st["configured"] is True and st["has_password"] is True
    # 密码永不回传，只回脱敏态
    assert "SA1234567890" not in json.dumps(st)
    assert "****" in st["password_masked"]
    # GET 同样脱敏
    g = _get_smtp(client, admin_jwt).json()
    assert g["user"] == "sender@163.com" and g["has_password"] is True
    assert "SA1234567890" not in json.dumps(g)


def test_smtp_empty_password_keeps_old(client, admin_jwt, models_file_backup, no_env_smtp):
    h = {"Authorization": f"Bearer {admin_jwt}"}
    assert client.put("/api/v1/admin/smtp-config", json={
        "host": "smtp.163.com", "port": 465, "user": "sender@163.com", "password": "OLD123456",
    }, headers=h).status_code == 200
    resp = client.put("/api/v1/admin/smtp-config", json={
        "host": "smtp.163.com", "port": 465, "user": "sender@163.com", "password": "",
    }, headers=h)
    assert resp.status_code == 200
    # 读回（明文解密后）确认旧密码未变
    with open(_MODELS_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    smtp_raw = raw.get("_smtp") or {}
    pw = smtp_raw.get("password")
    if isinstance(pw, dict):
        # 加密存储：直接断言未变（解密结果经 read_models_file）
        from api.v1.models_file import read_models_file
        assert read_models_file()["_smtp"]["password"] == "OLD123456"
    else:
        assert pw == "OLD123456"


def test_smtp_put_requires_host_user_password(client, admin_jwt, models_file_backup, no_env_smtp):
    # 显式清空（本地可能有真实后台配置，空密码=保旧的分支会误通过）
    from api.v1.models_file import write_models_file
    write_models_file({})
    h = {"Authorization": f"Bearer {admin_jwt}"}
    r1 = client.put("/api/v1/admin/smtp-config", json={"host": "", "user": "x", "password": "p"}, headers=h)
    assert r1.status_code == 400
    r2 = client.put("/api/v1/admin/smtp-config", json={"host": "smtp.163.com", "user": "", "password": "p"}, headers=h)
    assert r2.status_code == 400
    # 全新配置且密码空 → 400
    r3 = client.put("/api/v1/admin/smtp-config", json={"host": "smtp.163.com", "user": "x", "password": ""}, headers=h)
    assert r3.status_code == 400


# ---------------- 选择链：env 优先 → 后台配置 ----------------

def test_get_smtp_config_env_priority(monkeypatch, models_file_backup):
    import config.settings as s
    monkeypatch.setattr(s, "SMTP_HOST", "smtp.qq.com")
    monkeypatch.setattr(s, "SMTP_USER", "envuser@qq.com")
    monkeypatch.setattr(s, "SMTP_PASSWORD", "ENVPW")
    monkeypatch.setattr(s, "SMTP_FROM", "")
    from api.v1.models_file import write_models_file
    write_models_file({"_smtp": {"host": "smtp.163.com", "port": 465,
                                 "user": "admin@163.com", "password": "ADMINPW"}})
    cfg = s.get_smtp_config()
    assert cfg["host"] == "smtp.qq.com" and cfg["password"] == "ENVPW"


def test_get_smtp_config_falls_back_to_admin(monkeypatch, models_file_backup, no_env_smtp):
    import config.settings as s
    from api.v1.models_file import write_models_file
    write_models_file({"_smtp": {"host": "smtp.163.com", "port": 994,
                                 "user": "admin@163.com", "password": "ADMINPW",
                                 "from_addr": "", "use_ssl": True}})
    cfg = s.get_smtp_config()
    assert cfg["host"] == "smtp.163.com" and cfg["port"] == 994
    assert cfg["user"] == "admin@163.com" and cfg["password"] == "ADMINPW"
    assert cfg["from_addr"] == "admin@163.com"  # 空 from 回退 user
    # smtp_configured 经后台配置生效（无 env）
    from api.v1.auth.email_code import smtp_configured
    assert smtp_configured() is True


def test_get_smtp_config_empty(monkeypatch, models_file_backup, no_env_smtp):
    # 本地 models.json 可能已有真实后台配置（热配置）——显式清空构造未配置态
    from api.v1.models_file import write_models_file
    write_models_file({})
    import config.settings as s
    cfg = s.get_smtp_config()
    assert cfg["host"] == "" and cfg["password"] == ""
    from api.v1.auth.email_code import smtp_configured
    assert smtp_configured() is False


# ---------------- 测试发送端点 ----------------

def test_smtp_test_send_invalid_and_unconfigured(client, admin_jwt, models_file_backup, no_env_smtp, fake_redis, monkeypatch):
    from api.v1.auth import email_code as ec
    monkeypatch.setattr(ec, "smtp_configured", lambda: False)  # 显式未配置态
    h = {"Authorization": f"Bearer {admin_jwt}"}
    r1 = client.post("/api/v1/admin/smtp-config/test", json={"email": "bad"}, headers=h)
    assert r1.status_code == 422
    r2 = client.post("/api/v1/admin/smtp-config/test", json={"email": "a@b.com"}, headers=h)
    assert r2.status_code == 503  # 未配置


class _FakeRedis:
    def __init__(self):
        self.d = {}
        self.ttl_map = {}

    def get(self, k):
        return self.d.get(k)

    def set(self, k, v, ex=None):
        self.d[k] = str(v)
        if ex:
            self.ttl_map[k] = ex

    def ttl(self, k):
        return self.ttl_map.get(k, 0)


@pytest.fixture()
def fake_redis(monkeypatch):
    """隔离真实 Redis（冷却键跨测试残留会串扰）"""
    rds = _FakeRedis()
    monkeypatch.setattr("db.redis_client.get_redis", lambda: rds)
    return rds


def test_smtp_test_send_success(client, admin_jwt, models_file_backup, no_env_smtp, fake_redis, monkeypatch):
    from api.v1.auth import email_code as ec
    sent = {}
    monkeypatch.setattr(ec, "smtp_configured", lambda: True)
    monkeypatch.setattr(ec, "send_test_email", lambda to: sent.setdefault("to", to))
    h = {"Authorization": f"Bearer {admin_jwt}"}
    r = client.post("/api/v1/admin/smtp-config/test", json={"email": "me@163.com"}, headers=h)
    assert r.status_code == 200
    assert sent.get("to") == "me@163.com"


def test_smtp_test_send_cooldown(client, admin_jwt, models_file_backup, no_env_smtp, fake_redis, monkeypatch):
    from api.v1.auth import email_code as ec
    monkeypatch.setattr(ec, "smtp_configured", lambda: True)
    monkeypatch.setattr(ec, "send_test_email", lambda to: None)
    h = {"Authorization": f"Bearer {admin_jwt}"}
    r1 = client.post("/api/v1/admin/smtp-config/test", json={"email": "me@163.com"}, headers=h)
    assert r1.status_code == 200
    r2 = client.post("/api/v1/admin/smtp-config/test", json={"email": "me@163.com"}, headers=h)
    assert r2.status_code == 429
    assert "秒" in r2.json()["detail"]


# ---------------- 发件人显示名编码（中文头安全） ----------------

def test_send_email_from_header_chinese_display_name(monkeypatch, models_file_backup, no_env_smtp):
    """from_addr「小元AI <x@163.com>」中文显示名经 Header 编码——非 ASCII 头
    直接发会 UnicodeEncodeError（默认预填即该形态）"""
    import smtplib
    from api.v1.models_file import write_models_file
    write_models_file({"_smtp": {"host": "smtp.163.com", "port": 465,
                                 "user": "chengjie2017020@163.com", "password": "PW",
                                 "from_addr": "小元AI <chengjie2017020@163.com>", "use_ssl": True}})
    from api.v1.auth import email_code as ec

    captured = {}

    class _FakeSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def login(self, u, p):
            pass

        def sendmail(self, frm, to, msg):
            captured["msg"] = msg

        def quit(self):
            pass

    monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSMTP)
    ec._send_email("to@163.com", "123456")
    msg = captured["msg"]
    from_line = [l for l in msg.splitlines() if l.startswith("From:")][0]
    assert "chengjie2017020@163.com" in from_line
    # 头内显示名已编码为 =?utf-8?...?=（原始中文不进 From 头）
    assert "小元AI" not in from_line
    assert "=?utf-8?" in from_line
    # multipart/alternative：纯文本兜底 + HTML 大字验证码（part 内容 base64 编码，
    # 用 email 解析器解码后再断言）
    import email as _email
    parsed = _email.message_from_string(msg)
    assert parsed.get_content_type() == "multipart/alternative"
    parts = parsed.get_payload()
    types = {p.get_content_type() for p in parts}
    assert {"text/plain", "text/html"} <= types
    html_part = next(p for p in parts if p.get_content_type() == "text/html")
    html = html_part.get_payload(decode=True).decode("utf-8")
    assert "123456" in html and "letter-spacing:10px" in html


# ---------------- 授权码加密落盘（安全） ----------------

def test_smtp_password_encrypted_at_rest(monkeypatch, models_file_backup):
    """ENCRYPTION_PASSWORD 存在 → 授权码密文落盘；读回明文（透明加解密）"""
    monkeypatch.setenv("ENCRYPTION_PASSWORD", "test-enc-pwd")
    from api.v1.models_file import write_models_file, read_models_file
    write_models_file({"_smtp": {"host": "smtp.163.com", "port": 465,
                                 "user": "a@163.com", "password": "SECRETPW",
                                 "from_addr": "", "use_ssl": True}})
    with open(_MODELS_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    pw = raw["_smtp"]["password"]
    assert isinstance(pw, dict) and "encrypted_data" in pw  # 密文落盘
    assert "SECRETPW" not in json.dumps(raw)
    # 读回自动解密
    assert read_models_file()["_smtp"]["password"] == "SECRETPW"


if __name__ == "__main__":
    print("测试入口：pytest test/test_smtp_admin_config.py -v")
