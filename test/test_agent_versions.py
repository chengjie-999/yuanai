"""
Agent 多版本管理测试（2026-10-30）：上传不覆盖、版本清单、默认版本指定/删除、
version.json 兼容同步、用户下载清单端点鉴权。
"""
import os

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
        old = sess.query(User).filter_by(username="__ver_admin__").first()
        if old:
            sess.delete(old)
            sess.commit()
    finally:
        sess.close()
    r = db.register_user("__ver_admin__", "test1234", role="admin")
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
def tmp_downloads(tmp_path, monkeypatch):
    """隔离 downloads 目录（避免污染真实发布文件）"""
    import api.v1.admin.agent_devices as ad
    monkeypatch.setattr(ad, "root_path", lambda: str(tmp_path))
    yield str(tmp_path)


def _upload(client, ah, version: str, note: str = "", content: bytes = b"MZ-fake-exe"):
    import io
    files = {"file": (f"agent-{version}.exe", io.BytesIO(content), "application/octet-stream")}
    return client.post("/api/v1/admin/agent-exe-upload",
                       data={"version": version, "note": note}, files=files, headers=ah)


class TestAgentVersions:
    def test_upload_keeps_all_versions(self, client, admin_jwt, tmp_downloads):
        ah = {"Authorization": f"Bearer {admin_jwt}"}
        r1 = _upload(client, ah, "001", "首个版本")
        r2 = _upload(client, ah, "002", "第二个版本")
        assert r1.status_code == 200 and r2.status_code == 200
        data = client.get("/api/v1/admin/agent-versions", headers=ah).json()
        versions = {v["version"] for v in data["versions"]}
        assert {"001", "002"} <= versions  # 多版本共存
        assert data["default_version"] == "002"  # 最新版本自动成为默认（2026-10-31）
        # 文件落盘
        assert os.path.isfile(os.path.join(tmp_downloads, "downloads", "versions", "yuanai-agent-v001.exe"))
        # version.json 兼容同步：指向默认版本
        import json
        with open(os.path.join(tmp_downloads, "downloads", "version.json"), encoding="utf-8") as f:
            vj = json.load(f)
        assert vj["version"] == "002"
        assert "versions/yuanai-agent-v002.exe" in vj["exe"]
        assert vj["sha256"]

    def test_same_version_overwrites(self, client, admin_jwt, tmp_downloads):
        ah = {"Authorization": f"Bearer {admin_jwt}"}
        assert _upload(client, ah, "003", content=b"old").status_code == 200
        assert _upload(client, ah, "003", "修正版", content=b"new-content").status_code == 200
        data = client.get("/api/v1/admin/agent-versions", headers=ah).json()
        v3 = [v for v in data["versions"] if v["version"] == "003"]
        assert len(v3) == 1 and v3[0]["note"] == "修正版"  # 同版本覆盖不重复

    def test_set_default_and_delete_guards(self, client, admin_jwt, tmp_downloads):
        ah = {"Authorization": f"Bearer {admin_jwt}"}
        _upload(client, ah, "d001")
        _upload(client, ah, "d002")
        # 设默认 d002
        resp = client.post("/api/v1/admin/agent-versions/default",
                           json={"version": "d002"}, headers=ah)
        assert resp.status_code == 200
        assert client.get("/api/v1/admin/agent-versions", headers=ah).json()["default_version"] == "d002"
        # 删默认版本 → 允许，自动让位剩余最新（2026-10-31 用户拍板）
        resp = client.delete("/api/v1/admin/agent-versions/d002", headers=ah)
        assert resp.status_code == 200
        data = client.get("/api/v1/admin/agent-versions", headers=ah).json()
        assert data["default_version"] == "d001"
        # 删非默认 → ok
        resp = client.delete("/api/v1/admin/agent-versions/d001", headers=ah)
        assert resp.status_code == 200
        # 不存在的版本设默认 → 404
        assert client.post("/api/v1/admin/agent-versions/default",
                           json={"version": "nope"}, headers=ah).status_code == 404

    def test_version_name_validation(self, client, admin_jwt, tmp_downloads):
        ah = {"Authorization": f"Bearer {admin_jwt}"}
        assert _upload(client, ah, "bad/name").status_code == 400  # 路径穿越/非法字符
        assert _upload(client, ah, "a" * 40).status_code == 400  # 超长

    def test_user_downloads_endpoint(self, client, auth_headers, admin_jwt, tmp_downloads):
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        # 未登录 → 401
        assert client.get("/api/v1/agent/downloads").status_code == 401
        ah = {"Authorization": f"Bearer {admin_jwt}"}
        _upload(client, ah, "u001")
        # 登录用户可读清单（含默认标记）
        resp = client.get("/api/v1/agent/downloads", headers=auth_headers)
        assert resp.status_code == 200
        d = resp.json()
        assert d["default_version"] == "u001"
        assert any(v["version"] == "u001" for v in d["versions"])
