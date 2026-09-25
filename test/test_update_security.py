# -*- coding: utf-8 -*-
"""S1.7 自动更新供应链修复测试 — 上传 sha256 / 客户端强制 https / 校验矩阵

运行：pytest test/test_update_security.py -v
"""
import hashlib
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from utils.data_path import root_path  # noqa: E402


# ---------------- 纯函数 ----------------

def test_ver_lt():
    from agent.tray import _ver_lt
    assert _ver_lt("1.0.0", "1.0.1") is True
    assert _ver_lt("1.0.0", "1.1.0") is True
    assert _ver_lt("1.0.0", "2.0") is True
    assert _ver_lt("1.0.1", "1.0.0") is False
    assert _ver_lt("1.0.0", "1.0.0") is False
    assert _ver_lt("1.0.0", "1.0.0.1") is True


def test_insecure_update_allowed(monkeypatch):
    from agent.tray import AgentTray

    # https 始终允许
    assert AgentTray._insecure_update_allowed("https://cjyuanai.cn") is True
    # 公网 http 拒绝
    assert AgentTray._insecure_update_allowed("http://cjyuanai.cn") is False
    # localhost http：无 env 拒绝
    monkeypatch.delenv("AGENT_ALLOW_INSECURE_UPDATE", raising=False)
    assert AgentTray._insecure_update_allowed("http://127.0.0.1:8000") is False
    # localhost http + env 豁免
    monkeypatch.setenv("AGENT_ALLOW_INSECURE_UPDATE", "1")
    assert AgentTray._insecure_update_allowed("http://127.0.0.1:8000") is True
    assert AgentTray._insecure_update_allowed("http://localhost:8000") is True
    # env 豁免不覆盖公网 http
    assert AgentTray._insecure_update_allowed("http://example.com") is False


# ---------------- 客户端 _do_update 矩阵（本地 http.server + fake 托盘） ----------------

class _FakeIcon:
    def __init__(self):
        self.title = ""
        self.notes = []

    def notify(self, msg, title=""):
        self.notes.append(msg)

    def stop(self):
        pass


class _ManifestHandler(BaseHTTPRequestHandler):
    """/downloads/version.json 与 /downloads/yuanai-agent.exe（内容可配置）"""

    payload = b"FAKE-EXE-BYTES"

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/downloads/version.json":
            body = json.dumps(self.server.manifest).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/downloads/yuanai-agent.exe":
            self.send_response(200)
            self.send_header("Content-Length", str(len(self.payload)))
            self.end_headers()
            self.wfile.write(self.payload)
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture(scope="module")
def manifest_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _ManifestHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv
    srv.shutdown()


def _make_tray(server_url, tmp_path, monkeypatch):
    from agent.tray import AgentTray
    monkeypatch.setenv("AGENT_ALLOW_INSECURE_UPDATE", "1")

    obj = AgentTray.__new__(AgentTray)
    obj.server_url = server_url
    obj._icon = _FakeIcon()
    obj._running = True
    # 临时目录承接 new_exe / update.bat
    import agent.tray as tray_mod
    monkeypatch.setattr(tray_mod, "_config_file", lambda: tmp_path / "agent_config.json")
    # 拦截 bat 启动（真实执行会把测试机 python.exe 替换掉）
    import subprocess
    spawned = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: spawned.append(a))
    return obj, spawned


def test_do_update_public_http_rejected(manifest_server, tmp_path, monkeypatch):
    obj, _ = _make_tray("http://example.com", tmp_path, monkeypatch)
    monkeypatch.delenv("AGENT_ALLOW_INSECURE_UPDATE", raising=False)
    obj._do_update()
    assert any("https" in n for n in obj._icon.notes)
    assert not (tmp_path / "yuanai-agent.new").exists()


def test_do_update_missing_sha256_rejected(manifest_server, tmp_path, monkeypatch):
    manifest_server.manifest = {"version": "9.9.9", "exe": "/downloads/yuanai-agent.exe",
                                "size": len(_ManifestHandler.payload)}
    obj, spawned = _make_tray(f"http://127.0.0.1:{manifest_server.server_port}", tmp_path, monkeypatch)
    obj._do_update()
    assert any("sha256" in n for n in obj._icon.notes)
    assert not (tmp_path / "yuanai-agent.new").exists()
    assert not (tmp_path / "update.bat").exists()
    assert not spawned  # 未写自替换脚本


def test_do_update_hash_mismatch_rejected(manifest_server, tmp_path, monkeypatch):
    manifest_server.manifest = {"version": "9.9.9", "exe": "/downloads/yuanai-agent.exe",
                                "size": len(_ManifestHandler.payload),
                                "sha256": "0" * 64}
    obj, spawned = _make_tray(f"http://127.0.0.1:{manifest_server.server_port}", tmp_path, monkeypatch)
    obj._do_update()
    assert any("校验失败" in n for n in obj._icon.notes)
    # 临时文件必须被删除，且绝不写 update.bat
    assert not (tmp_path / "yuanai-agent.new").exists()
    assert not (tmp_path / "update.bat").exists()
    assert not spawned


def test_do_update_hash_match_proceeds(manifest_server, tmp_path, monkeypatch):
    digest = hashlib.sha256(_ManifestHandler.payload).hexdigest()
    manifest_server.manifest = {"version": "9.9.9", "exe": "/downloads/yuanai-agent.exe",
                                "size": len(_ManifestHandler.payload), "sha256": digest}
    obj, spawned = _make_tray(f"http://127.0.0.1:{manifest_server.server_port}", tmp_path, monkeypatch)
    obj._do_update()
    # 校验通过：留下 .new + 写 update.bat（Popen 已拦截，未真实执行）
    assert (tmp_path / "yuanai-agent.new").read_bytes() == _ManifestHandler.payload
    assert (tmp_path / "update.bat").exists()
    assert spawned
    # 手动清理
    (tmp_path / "yuanai-agent.new").unlink()
    (tmp_path / "update.bat").unlink()


# ---------------- 后端上传（流式 sha256 落 version.json） ----------------

def test_upload_writes_sha256(client, monkeypatch, tmp_path):
    """上传 exe → version.json 含正确 sha256/size（root_path 打桩到 tmp，不碰真实 downloads/）"""
    import api.v1.admin.agent_devices as ad
    from api.v1.auth.utils import create_token
    from db.session import get_db

    monkeypatch.setattr(ad, "root_path", lambda: str(tmp_path))

    # 自建/复用 admin 测试用户（不依赖环境账号）
    db = get_db()
    from db.session import User
    sess = db.Session()
    try:
        u = sess.query(User).filter_by(username="__sse_admin_test__").first()
        if not u:
            sess.close()
            r = db.register_user("__sse_admin_test__", "test123", role="admin")
            uid = r["id"]
        else:
            uid = u.id
    finally:
        sess.close()

    payload = b"MZ" + os.urandom(64 * 1024)  # 假 exe 头 + 随机体
    resp = client.post(
        "/api/v1/admin/agent-exe-upload",
        headers={"Authorization": f"Bearer {create_token(uid, 'admin')}"},
        data={"version": "9.9.9"},
        files={"file": ("yuanai-agent.exe", payload, "application/octet-stream")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["sha256"] == hashlib.sha256(payload).hexdigest()

    manifest = json.loads((tmp_path / "downloads" / "version.json").read_text(encoding="utf-8"))
    assert manifest["sha256"] == hashlib.sha256(payload).hexdigest()
    assert manifest["size"] == len(payload)
    assert manifest["min_version"] == "9.9.9"
    # 服务端落盘内容与上传一致
    assert (tmp_path / "downloads" / "yuanai-agent.exe").read_bytes() == payload


if __name__ == "__main__":
    print("测试入口：pytest test/test_update_security.py -v")
