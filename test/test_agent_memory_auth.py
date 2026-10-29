# -*- coding: utf-8 -*-
"""C2 记忆接口 IDOR 修复测试（2026-10-29）：
任意设备凭据不能读/写/删他人记忆——目标用户强制为设备一对一绑定用户；
bridge-memory 仅桥接专用设备可用。零网络：鉴权与绑定 mock。"""
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from api.v1.agent import router as ar  # noqa: E402


def _req(headers=None):
    return SimpleNamespace(headers=headers or {})


def test_memory_requires_bound_device(monkeypatch):
    """未绑定设备 → 403（不再信任任意 user_id）"""
    monkeypatch.setattr(ar, "_verify_agent_secret", lambda aid, secret: True)
    monkeypatch.setattr(ar, "resolve_agent_uid", lambda aid: None)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        ar.agent_get_memory(_req({"X-Agent-Id": "9", "X-Agent-Secret": "s"}), user_id=999)
    assert e.value.status_code == 403


def test_memory_ignores_arbitrary_user_id(monkeypatch, tmp_path):
    """绑定设备 + 伪造他人 user_id → 实际操作绑定用户自己的记忆"""
    import yuanai_core.memory_store as store
    monkeypatch.setattr(store, "root_path", lambda: str(tmp_path))
    monkeypatch.setattr(ar, "_verify_agent_secret", lambda aid, secret: True)
    monkeypatch.setattr(ar, "resolve_agent_uid", lambda aid: 42)  # 设备绑定用户 42
    import db.session as dbs
    db = dbs.get_db()
    monkeypatch.setattr(dbs, "get_db", lambda: db)
    monkeypatch.setattr(db, "merge_user_memory",
                        lambda uid, facts, mi, mc: {"added": len(facts)})
    r = ar.agent_add_memory(_req({"X-Agent-Id": "9", "X-Agent-Secret": "s"}),
                            ar.AgentMemoryBody(user_id=999, facts=["测试"]))
    assert r["added"] == 1  # 写入走的是绑定用户 42（merge_user_memory 被 mock）


def test_bridge_memory_rejects_non_bridge_device(monkeypatch):
    monkeypatch.setattr(ar, "_verify_agent_secret", lambda aid, secret: True)
    import config.settings as s
    monkeypatch.setattr(s, "CLAUDE_BRIDGE_AGENT_ID", 77)  # 桥接专用设备 77
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        ar.bridge_memory(_req({"X-Agent-Id": "9", "X-Agent-Secret": "s"}),
                         ar.BridgeMemoryBody(user_id=999, facts=["x"]))
    assert e.value.status_code == 403


def test_bridge_memory_allows_bridge_device(monkeypatch):
    monkeypatch.setattr(ar, "_verify_agent_secret", lambda aid, secret: True)
    import config.settings as s
    monkeypatch.setattr(s, "CLAUDE_BRIDGE_AGENT_ID", 77)
    import db.session as dbs
    db = dbs.get_db()
    monkeypatch.setattr(dbs, "get_db", lambda: db)
    monkeypatch.setattr(db, "merge_user_memory", lambda uid, facts, mi, mc: {"added": 1})
    r = ar.bridge_memory(_req({"X-Agent-Id": "77", "X-Agent-Secret": "s"}),
                         ar.BridgeMemoryBody(user_id=999, facts=["x"]))
    assert r == {"ok": True, "added": 1}
