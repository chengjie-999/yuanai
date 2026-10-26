# -*- coding: utf-8 -*-
"""O1/O3 活动上报端点测试（2026-10-26）：无 WS 客户端（yuancc hooks）的
元数据活动上报 + 状态合并展示。零网络：_verify_agent_secret 与 token 校验 mock"""
import asyncio
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from api.v1.agent import router as ar  # noqa: E402


@pytest.fixture
def authed(monkeypatch):
    monkeypatch.setattr(ar, "_verify_agent_secret", lambda aid, secret: True)
    monkeypatch.setattr(ar, "_agents", {})
    monkeypatch.setattr(ar, "_agent_info", {})
    monkeypatch.setattr(ar, "_rest_activities", {})
    return ar


def _req(headers=None):
    return SimpleNamespace(headers=headers or {})


def test_report_activity_requires_creds():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        asyncio.run(ar.report_activity(ar.ActivityReport(state="working", tool="Bash"), _req()))
    assert e.value.status_code == 401


def test_report_activity_records_metadata(authed):
    from fastapi import HTTPException
    r = asyncio.run(ar.report_activity(ar.ActivityReport(state="working", tool="Bash"),
                           _req({"X-Agent-Id": "7", "X-Agent-Secret": "s"})))
    assert r == {"ok": True}
    acts = ar._rest_activities["7"]
    assert acts[-1]["message"] == "工具调用: Bash"
    assert acts[-1]["source"] == "rest"
    # 元数据约束：只收状态/工具名，无内容字段
    assert "content" not in acts[-1]


def test_report_activity_caps_list(authed):
    for i in range(25):
        asyncio.run(ar.report_activity(ar.ActivityReport(state="thinking"),
                           _req({"X-Agent-Id": "7", "X-Agent-Secret": "s"})))
    assert len(ar._rest_activities["7"]) == 20


def test_status_includes_offline_rest_activity(authed, monkeypatch):
    asyncio.run(ar.report_activity(ar.ActivityReport(state="working", tool="Bash"),
                       _req({"X-Agent-Id": "7", "X-Agent-Secret": "s"})))
    monkeypatch.setattr("api.v1.middleware._extract_token", lambda r: "t")
    monkeypatch.setattr("api.v1.auth.utils.verify_token",
                        lambda t: {"user_id": 1, "role": "admin", "username": "admin"})
    status = ar._get_agent_status(_req(), include_activities=True)
    entry = next(e for e in status if e["agent_id"] == "7")
    assert entry["online"] is False
    assert "离线上报" in entry["agent_name"]
    assert entry["activities"][0]["message"] == "工具调用: Bash"


def test_status_merges_ws_and_rest(authed, monkeypatch):
    # 在线设备：WS 活动 + REST 活动合并展示
    ar._agents["7"] = object()
    ar._agent_info["7"] = {"agent_name": "本机", "capabilities": [], "activities": [
        {"message": "WS活动", "detail": "", "time": "10:00:00"}]}
    asyncio.run(ar.report_activity(ar.ActivityReport(state="thinking"),
                       _req({"X-Agent-Id": "7", "X-Agent-Secret": "s"})))
    merged = ar._merged_activities("7")
    msgs = [m["message"] for m in merged]
    assert "WS活动" in msgs and "思考中" in msgs
    assert len(merged) == 2
