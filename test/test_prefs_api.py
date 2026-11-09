# -*- coding: utf-8 -*-
"""多端同步 P1 测试（2026-11-09）——用户偏好上云：白名单校验 / GET/PUT / 登录响应 agreed

运行：pytest test/test_prefs_api.py -v
"""
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # noqa: E402
sys.stdout.reconfigure(encoding='utf-8')

from api.v1.auth.router import _sanitize_prefs  # noqa: E402


def test_sanitize_whitelist():
    """白名单五键通过；未知键/非法值丢弃（fail-soft）"""
    clean = _sanitize_prefs({
        "entertainmentMode": "1",
        "chatBackend": "local",
        "autoRead": "0",
        "dmTargets": {"s1": "claude", "s2": "automation"},
        "activeTargets": {"s3": "claude"},
        "hacker_key": "x",                      # 未知键丢弃
        "chatBackend_extra": "bad",
    })
    assert clean == {
        "entertainmentMode": "1",
        "chatBackend": "local",
        "autoRead": "0",
        "dmTargets": {"s1": "claude", "s2": "automation"},
        "activeTargets": {"s3": "claude"},
    }


def test_sanitize_invalid_values_dropped():
    clean = _sanitize_prefs({
        "entertainmentMode": "true",            # 非 0/1 丢弃
        "chatBackend": "hybrid",                # 非法后端丢弃
        "autoRead": "maybe",
        "dmTargets": {"s1": "hacker"},          # 非法目标丢弃（条目级）
        "activeTargets": ["claude"],            # 非 dict 丢弃
    })
    assert clean == {"dmTargets": {}}


def test_sanitize_map_size_cap():
    big = {f"s{i}": "claude" for i in range(60)}
    clean = _sanitize_prefs({"dmTargets": big})
    assert "dmTargets" not in clean  # 超 50 条整键丢弃


def test_prefs_get_put_roundtrip(client, auth_headers):
    if not auth_headers:
        pytest.skip("登录失败（本地 MySQL 不可用？）")
    # 可读（初始内容可能是前次运行残留，不断言空）
    r = client.get("/api/v1/auth/prefs", headers=auth_headers)
    assert r.status_code == 200 and isinstance(r.json()["prefs"], dict)
    # PUT 合并写入
    r = client.put("/api/v1/auth/prefs", headers=auth_headers,
                   json={"prefs": {"entertainmentMode": "1", "chatBackend": "cloud"}})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["prefs"]["entertainmentMode"] == "1"
    # GET 读回
    r = client.get("/api/v1/auth/prefs", headers=auth_headers)
    prefs = r.json()["prefs"]
    assert prefs["entertainmentMode"] == "1" and prefs["chatBackend"] == "cloud"
    # 二次 PUT 合并不丢旧键
    client.put("/api/v1/auth/prefs", headers=auth_headers,
               json={"prefs": {"autoRead": "0"}})
    prefs = client.get("/api/v1/auth/prefs", headers=auth_headers).json()["prefs"]
    assert prefs["autoRead"] == "0" and prefs["entertainmentMode"] == "1"
    # 清理测试数据（避免污染其他测试）
    client.put("/api/v1/auth/prefs", headers=auth_headers,
               json={"prefs": {"entertainmentMode": "0", "chatBackend": "auto", "autoRead": "1"}})


def test_login_response_has_agreed(client, auth_headers):
    if not auth_headers:
        pytest.skip("登录失败（本地 MySQL 不可用？）")
    r = client.post("/api/v1/auth/login",
                    json={"username": "__test_api_user__", "password": "test1234"})
    assert r.status_code == 200
    user = r.json()["user"]
    assert "agreed" in user and isinstance(user["agreed"], bool)  # 服务端留痕字段存在
