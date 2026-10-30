"""
更新公告测试（2026-10-31 用户拍板）：网站部署与 Agent 版本更新各发一条公告。
覆盖：列表/手动发布/删除/权限；部署钩子幂等（同 commit 不重复）；上传 Agent 自动公告。
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
        old = sess.query(User).filter_by(username="__ann_admin__").first()
        if old:
            sess.delete(old)
            sess.commit()
    finally:
        sess.close()
    r = db.register_user("__ann_admin__", "test1234", role="admin")
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
def tmp_ann(monkeypatch, tmp_path):
    """隔离公告存储文件"""
    import api.v1.announcements as ann
    monkeypatch.setattr(ann, "root_path", lambda: str(tmp_path))
    yield


class TestAnnouncements:
    def test_publish_list_delete_and_auth(self, client, admin_jwt, tmp_ann):
        ah = {"Authorization": f"Bearer {admin_jwt}"}
        # 普通用户（无 token 场景）→ 401；auth_headers 用户可读列表
        assert client.get("/api/v1/announcements").status_code == 401
        # 管理员发布
        resp = client.post("/api/v1/admin/announcements",
                           json={"title": "测试公告", "content": "内容", "kind": "site"},
                           headers=ah)
        assert resp.status_code == 200
        ann_id = resp.json()["announcement"]["id"]
        # 列表可见
        rows = client.get("/api/v1/announcements", headers=ah).json()
        assert any(a["id"] == ann_id and a["kind"] == "site" for a in rows)
        # 非法 kind → 422
        assert client.post("/api/v1/admin/announcements",
                           json={"title": "x", "content": "y", "kind": "bad"},
                           headers=ah).status_code == 422
        # 删除
        resp = client.delete(f"/api/v1/admin/announcements/{ann_id}", headers=ah)
        assert resp.status_code == 200
        assert not any(a["id"] == ann_id for a in client.get("/api/v1/announcements", headers=ah).json())
        # 再删 → 404
        assert client.delete(f"/api/v1/admin/announcements/{ann_id}", headers=ah).status_code == 404

    def test_deploy_announcement_idempotent(self, monkeypatch, tmp_ann):
        """部署钩子：commit 变化发一条；同 commit 重启不重复"""
        import api.v1.announcements as ann
        import subprocess as _sp

        class _R:
            def __init__(self, out):
                self.stdout = out
                self.stderr = ""

        heads = iter(["abc12345", "abc12345", "def67890"])
        monkeypatch.setattr(_sp, "run", lambda *a, **k: _R(next(heads)))
        ann.auto_deploy_announcement()  # 首次 → 发一条
        ann.auto_deploy_announcement()  # 同 commit → 不发
        assert len(ann._load()) == 1
        ann.auto_deploy_announcement()  # 新 commit → 再发一条
        assert len(ann._load()) == 2
        assert all(a["kind"] == "site" for a in ann._load())

    def test_agent_upload_auto_announcement(self, client, admin_jwt, tmp_ann, monkeypatch, tmp_path):
        """上传 Agent 新版本 → 自动发 agent 公告（复用版本管理测试的隔离套路）"""
        import api.v1.admin.agent_devices as ad
        import api.v1.announcements as ann
        monkeypatch.setattr(ad, "root_path", lambda: str(tmp_path))
        monkeypatch.setattr(ann, "root_path", lambda: str(tmp_path))
        ah = {"Authorization": f"Bearer {admin_jwt}"}
        import io
        resp = client.post("/api/v1/admin/agent-exe-upload",
                           data={"version": "ann1", "note": "公告测试"},
                           files={"file": ("x.exe", io.BytesIO(b"MZ-fake"), "application/octet-stream")},
                           headers=ah)
        assert resp.status_code == 200
        rows = ann._load()
        assert any(a["kind"] == "agent" and "ann1" in a["title"] for a in rows)
