# -*- coding: utf-8 -*-
"""记忆工具路径判定测试 — 云端直连 vs 本地 Agent HTTP（无 MySQL 依赖）

部署后「记忆失效」根因回归（2026-10-12）：原「试连 MySQL」判定在用户电脑上
连到本机开发 MySQL，记忆写进本地库云端永远读不到；HTTP 回退的 GET/DELETE
还丢 user_id（云端 400）。判定规则：
  APP_HOME / APP_ENV=production（云端容器）→ direct
  identity.server_url 指向远程云端      → http（GET/DELETE 必须带 user_id）
  identity.server_url 指向 localhost / 无 identity → direct（本地联调同库）
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from yuanai_core.tools import user_memory as um


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("APP_HOME", "APP_ENV"):
        monkeypatch.delenv(k, raising=False)


def _fake_http(monkeypatch):
    """拦截 urllib 请求，记录 (url, method, body) 并返回全形状 ok 响应"""
    calls = []

    class _Resp:
        def __init__(self, payload):
            self._b = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        def read(self):
            return self._b

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_open(req, timeout=None):
        calls.append((req.full_url, req.get_method(), req.data))
        return _Resp({"ok": True, "memory": "", "added": 0,
                      "deleted": 0, "asked_more": False})

    monkeypatch.setattr(um.urllib.request, "urlopen", fake_open)
    return calls


# ---------------- 路径判定 ----------------

def test_cloud_container_direct_even_with_remote_identity(monkeypatch):
    """云端容器（APP_HOME）→ 直连，不受 identity 影响（容器卷残留旧身份曾致 401）"""
    monkeypatch.setenv("APP_HOME", "/app")
    monkeypatch.setattr(um, "_read_identity", lambda: {"server_url": "wss://cjyuanai.cn"})
    assert um._memory_path() == "direct"


def test_production_env_direct(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(um, "_read_identity", lambda: {"server_url": "wss://cjyuanai.cn"})
    assert um._memory_path() == "direct"


def test_remote_server_identity_http(monkeypatch):
    """本地 Agent 指向远程云端 → HTTP（本机 MySQL 是开发库，直连会把记忆写丢）"""
    monkeypatch.setattr(um, "_read_identity", lambda: {"server_url": "wss://cjyuanai.cn"})
    assert um._memory_path() == "http"


def test_localhost_identity_direct(monkeypatch):
    """本地开发联调（agent 连 localhost API）→ 直连本机库，与 API 同库一致"""
    monkeypatch.setattr(um, "_read_identity", lambda: {"server_url": "ws://localhost:8000"})
    assert um._memory_path() == "direct"


def test_no_identity_direct(monkeypatch):
    monkeypatch.setattr(um, "_read_identity", lambda: {})
    assert um._memory_path() == "direct"


# ---------------- HTTP 回退必须带 user_id ----------------

def test_http_get_carries_user_id(monkeypatch):
    """回归：GET /memory 丢 user_id → 云端 400「缺少 user_id」"""
    monkeypatch.setattr(um, "_read_identity", lambda: {"server_url": "wss://cjyuanai.cn"})
    calls = _fake_http(monkeypatch)
    r = um._call_memory("/memory", "GET", uid=3)
    assert r["ok"] is True
    assert len(calls) == 1
    url, method, body = calls[0]
    assert method == "GET" and "?user_id=3" in url


def test_http_post_carries_user_id(monkeypatch):
    monkeypatch.setattr(um, "_read_identity", lambda: {"server_url": "wss://cjyuanai.cn"})
    calls = _fake_http(monkeypatch)
    r = um._call_memory("/memory", "POST", {"facts": ["用户怕辣"]}, uid=3)
    assert r["ok"] is True
    assert len(calls) == 1
    _, method, body = calls[0]
    data = json.loads(body.decode("utf-8"))
    assert method == "POST" and data["user_id"] == 3 and data["facts"] == ["用户怕辣"]


def test_http_delete_carries_user_id(monkeypatch):
    """回归：DELETE /memory body 丢 user_id → 云端 400「缺少 user_id 或 line」"""
    monkeypatch.setattr(um, "_read_identity", lambda: {"server_url": "wss://cjyuanai.cn"})
    calls = _fake_http(monkeypatch)
    r = um._call_memory("/memory", "DELETE", {"line": "用户怕辣"}, uid=3)
    assert r["ok"] is True
    assert len(calls) == 1
    _, method, body = calls[0]
    data = json.loads(body.decode("utf-8"))
    assert method == "DELETE" and data["user_id"] == 3 and data["line"] == "用户怕辣"


def test_http_organize_maps_to_post_with_uid_and_session(monkeypatch):
    """ORGANIZE 落 HTTP POST，带 user_id/session_id/items（自整理工具走本地 Agent 的通道）"""
    monkeypatch.setattr(um, "_read_identity", lambda: {"server_url": "wss://cjyuanai.cn"})
    calls = _fake_http(monkeypatch)
    r = um._call_memory("/memory/organize", "ORGANIZE",
                        {"session_id": "s1", "items": ["a\nb"]}, uid=3)
    assert r["ok"] is True
    assert len(calls) == 1
    url, method, body = calls[0]
    data = json.loads(body.decode("utf-8"))
    assert "/memory/organize" in url and method == "POST"
    assert data["user_id"] == 3 and data["session_id"] == "s1" and data["items"] == ["a\nb"]


# ---------------- file 工具 None 防御（LLM 兜底尝试曾崩 len(None)） ----------------

def test_read_data_file_missing_returns_friendly(monkeypatch):
    from yuanai_core.tools import file_tools
    monkeypatch.setattr(file_tools, "_read", lambda path: None)
    out = file_tools.read_data_file.invoke({"path": "data/.yuan/nope.md"})
    assert "不存在" in out


if __name__ == "__main__":
    print("测试入口：pytest test/test_user_memory_routing.py -v")
