"""T2 免输码自动注册测试（2026-11-06）

覆盖：exe 文件名解析安装码（正常/改名/无码）；带码下载端点（码归属校验/
Content-Disposition 文件名）；register_device 静默注册（mock 云端）。
"""
import io
import json
import secrets

import pytest

from agent.main import install_code_from_exe_name, register_device
from db.session import get_db


def test_install_code_from_exe_name():
    import sys
    old_exe, old_argv = getattr(sys, "executable", None), list(sys.argv)
    try:
        sys.executable = r"C:\Program Files\XiaoYuanAI\bin\yuanai-agent-v20261105_YUAN-ABCD-1234-5678.exe"
        sys.argv = [sys.executable]
        assert install_code_from_exe_name() == "YUAN-ABCD-1234-5678"
        # 改名（安装器重命名）→ 解析不到 → 兜底弹窗路径
        sys.executable = r"C:\Program Files\XiaoYuanAI\bin\小元AI.exe"
        sys.argv = [sys.executable]
        assert install_code_from_exe_name() == ""
        # 小写也兼容
        sys.executable = r"C:\tmp\yuanai-agent-v1.0_yuan-abcd-1234-5678.exe"
        sys.argv = [sys.executable]
        assert install_code_from_exe_name() == "YUAN-ABCD-1234-5678"
    finally:
        sys.executable = old_exe
        sys.argv = old_argv


def test_register_device_silent(monkeypatch, tmp_path):
    """静默注册：POST /agent/register → 身份落盘（失败抛异常供兜底）"""
    captured = {}

    class _Resp:
        def read(self):
            return json.dumps({"agent_id": "77", "agent_secret": "SECRET",
                               "machine_name": "PC"}).encode()

    def _fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["code"] = captured["body"]["install_code"]
        return _Resp()

    import urllib.request as _ur
    monkeypatch.setattr(_ur, "urlopen", _fake_urlopen)
    import agent.main as am
    monkeypatch.setattr(am, "IDENTITY_FILE", str(tmp_path / "identity.json"))
    ident = register_device("ws://localhost:8000", "YUAN-AAA-BBB-CCC")
    assert ident["agent_id"] == "77" and ident["agent_secret"] == "SECRET"
    assert captured["url"].startswith("http://localhost:8000/api/v1/agent/register")
    assert captured["code"] == "YUAN-AAA-BBB-CCC"
    with open(am.IDENTITY_FILE, encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["server_url"] == "ws://localhost:8000"


# ---------------- 带码下载端点 ----------------

def _db_or_skip():
    try:
        return get_db()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


@pytest.fixture(scope="module")
def db():
    return _db_or_skip()


@pytest.fixture()
def exe_file(tmp_path, monkeypatch):
    """假 exe 文件 + versions 清单（端点函数内导入 _downloads_dir，patch 源模块即可）"""
    d = tmp_path / "downloads" / "versions"
    d.mkdir(parents=True)
    exe = d / "yuanai-agent-v9.9.exe"
    exe.write_bytes(b"MZ-fake-exe")
    from api.v1.admin import agent_devices as ad
    monkeypatch.setattr(ad, "_downloads_dir", lambda: str(tmp_path / "downloads"))
    return str(tmp_path)


@pytest.fixture()
def versions_manifest(exe_file):
    from api.v1.admin.agent_devices import _save_versions
    _save_versions({
        "default_version": "9.9",
        "versions": [{"version": "9.9", "filename": "yuanai-agent-v9.9.exe",
                      "size": 11, "sha256": "", "uploaded_at": "2026-11-06", "note": ""}],
    })


@pytest.fixture()
def my_code_user(db):
    """用户 + 预绑定安装码"""
    from db.session import AgentDevice, User
    with db.session() as sess:
        u = sess.query(User).filter_by(username="__t2_user__").first()
        if u is None:
            r = db.register_user("__t2_user__", "test1234")
            u = sess.query(User).filter_by(id=r["id"]).first()
        uid = u.id
        code = "YUAN-" + "-".join(secrets.token_hex(2).upper() for _ in range(3))
        dev = AgentDevice(install_code=code, agent_secret="", user_id=uid)
        sess.add(dev)
        sess.commit()
    yield uid, code
    with db.session() as sess:
        for dev in sess.query(AgentDevice).filter(AgentDevice.user_id == uid).all():
            sess.delete(dev)
            sess.commit()


def _jwt(db, uid):
    from api.v1.auth.utils import create_token
    return create_token(uid, "user", "t2user")


def test_download_exe_with_code_filename(client, db, exe_file, versions_manifest, my_code_user):
    uid, code = my_code_user
    h = {"Authorization": f"Bearer {_jwt(db, uid)}"}
    r = client.get(f"/api/v1/agent/download-exe?code={code}", headers=h)
    assert r.status_code == 200
    cd = r.headers.get("content-disposition", "")
    assert f"yuanai-agent-v9.9_{code}.exe" in cd
    assert r.content == b"MZ-fake-exe"


def test_download_exe_code_ownership(client, db, exe_file, versions_manifest, my_code_user):
    uid, code = my_code_user
    h = {"Authorization": f"Bearer {_jwt(db, uid)}"}
    # 别人的码 → 403
    r = client.get("/api/v1/agent/download-exe?code=YUAN-DEAD-BEEF-0000", headers=h)
    assert r.status_code == 403
    # 未登录 → 401
    assert client.get(f"/api/v1/agent/download-exe?code={code}").status_code == 401


def test_download_exe_without_code_plain_filename(client, db, exe_file, versions_manifest, my_code_user):
    uid, _ = my_code_user
    h = {"Authorization": f"Bearer {_jwt(db, uid)}"}
    r = client.get("/api/v1/agent/download-exe", headers=h)
    assert r.status_code == 200
    assert "yuanai-agent-v9.9.exe" in r.headers.get("content-disposition", "")


if __name__ == "__main__":
    print("测试入口：pytest test/test_agent_code_download.py -v")
