# -*- coding: utf-8 -*-
"""本地设置面板测试（2026-11-11 网页化）——状态/开关/工作目录/重注册/更新/退出（零网络）

运行：pytest test/test_panel.py -v
"""
import json
import os
import sys
import urllib.request
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # noqa: E402
sys.stdout.reconfigure(encoding='utf-8')

from agent.panel import PanelServer  # noqa: E402


class FakeTray:
    """面板 API 依赖的托盘最小面"""

    def __init__(self):
        self.toggles = {"analysis": True, "collection": True, "automation": True, "claude": True}
        self._status = "online"
        self._profile_label = "测试用户"
        self._update_available = None
        self._update_forced = False
        self._reinstall_prompted = True
        self.server_url = "wss://example.test"
        self.agent_id = "1"
        self.agent_token = "s"
        self.saved = []
        self.restarted = []
        self.updated = []

    def _trigger_restart(self):
        self.restarted.append(1)

    def _restart_loops(self):
        self.restarted.append(1)

    def _reinstall_flow(self, why, code=""):
        return (True, "") if code else (False, "未输入安装码")

    def _check_update_once(self, manual=False):
        self._update_available = "20261111"

    def _do_update(self):
        self.updated.append(1)


@pytest.fixture
def panel(monkeypatch, tmp_path):
    """起真实本地 HTTP 服务（127.0.0.1 随机端口），托盘逻辑全部打桩"""
    import agent.tray as tray_mod
    tray = FakeTray()
    # save_toggles 落盘到 tmp（面板 toggle API 会调 tray.save_toggles）
    monkeypatch.setattr(tray_mod, "save_toggles", lambda toggles: tray.saved.append(dict(toggles)))

    def fake_pick(*a, **k):
        return "C:\\Users\\test\\repo"

    import agent.cc_workspace as ccw
    monkeypatch.setattr(ccw, "pick_directory", fake_pick)
    monkeypatch.setattr(ccw, "set_project_dir", lambda p: p)  # 校验不依赖真实目录

    srv = PanelServer(tray)
    srv.start()
    yield srv, tray
    srv.stop()


def _get(url, expect=200):
    with urllib.request.urlopen(url, timeout=5) as r:
        body = r.read()
        if "application/json" in (r.headers.get("Content-Type") or ""):
            return r.status, json.loads(body)
        return r.status, body


def _post(url, body=None, expect=200):
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def test_panel_page_served(panel):
    srv, _ = panel
    status, body = _get(srv.url)
    assert status == 200
    html = body.decode("utf-8")
    assert "小元AI Agent 设置" in html
    assert "--accent" in html          # 网站配色变量对齐
    assert "breathe" in html           # 吉祥物呼吸核心
    assert "选择文件夹" in html


def test_status_endpoint(panel):
    srv, _ = panel
    status, data = _get(f"http://127.0.0.1:{srv._port}/api/status")
    assert status == 200 and data["ok"] is True
    assert data["status"] == "online"
    assert data["profile"] == "测试用户"
    assert data["toggles"]["claude"] is True


def test_toggle_switch(panel):
    srv, tray = panel
    status, data = _post(f"http://127.0.0.1:{srv._port}/api/toggle",
                         {"key": "claude", "enabled": False})
    assert status == 200 and data["ok"] is True
    assert tray.toggles["claude"] is False
    assert tray.restarted  # 开关切换 → 重连生效


def test_toggle_unknown_key(panel):
    srv, _ = panel
    status, data = _post(f"http://127.0.0.1:{srv._port}/api/toggle",
                         {"key": "hacker", "enabled": True})
    assert data["ok"] is False


def test_pick_workspace(panel):
    srv, _ = panel
    status, data = _post(f"http://127.0.0.1:{srv._port}/api/pick-workspace")
    assert data["ok"] is True and "repo" in data["path"]


def test_reinstall_with_code(panel):
    srv, _ = panel
    status, data = _post(f"http://127.0.0.1:{srv._port}/api/reinstall",
                         {"code": "YUAN-123"})
    assert data["ok"] is True
    status, data2 = _post(f"http://127.0.0.1:{srv._port}/api/reinstall", {"code": ""})
    assert data2["ok"] is False and "不能为空" in data2["error"]


def test_check_update(panel):
    srv, _ = panel
    status, data = _post(f"http://127.0.0.1:{srv._port}/api/check-update")
    assert data["update_available"] is True and data["version"] == "20261111"


def test_404(panel):
    srv, _ = panel
    try:
        _get(f"http://127.0.0.1:{srv._port}/nope")
        assert False
    except urllib.error.HTTPError as e:
        assert e.code == 404
