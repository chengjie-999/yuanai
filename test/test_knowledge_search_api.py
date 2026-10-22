# -*- coding: utf-8 -*-
"""知识检索双路径测试 — 部署 Agent 经云端 /agent/knowledge/search（设备凭据）

回归背景（2026-10-22）：部署 Agent 曾直连本机 Milvus（用户电脑没有），
连接重试挂死对话 120s。修复后：
- 云端端点：设备凭据鉴权 + 用户由设备绑定推导（body user_id 冗余校验）
- knowledge_tool：is_remote_agent 判定双路径（http / 直连）
- rag._get_db：连接失败进入冷却期快速失败（不再每轮重试）
"""
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')


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
def env(db):
    """用户 + 绑定设备（secret 已知）"""
    from db.session import AgentDevice, User
    uid = db.register_user("__kb_agent__", "test123")["id"]
    secret = "kb-secret-" + uuid.uuid4().hex[:12]
    dev = AgentDevice(install_code="KB-" + uuid.uuid4().hex[:8], agent_secret=secret,
                      machine_name="kb-test", user_id=uid)
    sess = db.Session()
    try:
        sess.add(dev)
        sess.commit()
        dev_id = dev.id
    finally:
        sess.close()
    yield {"uid": uid, "agent_id": dev_id, "secret": secret}
    sess = db.Session()
    try:
        sess.query(AgentDevice).filter_by(id=dev_id).delete()
        u = sess.query(User).filter_by(id=uid).first()
        if u:
            sess.delete(u)
        sess.commit()
    finally:
        sess.close()


def _hdrs(env, agent_id=None, secret=None):
    return {"X-Agent-Id": str(agent_id if agent_id is not None else env["agent_id"]),
            "X-Agent-Secret": secret if secret is not None else env["secret"]}


# ---------------- 云端端点 ----------------

def test_knowledge_search_auth_matrix(client, db, env, monkeypatch):
    """坏凭据 401 / 未绑定 403 / user_id 不符 403 / 缺 query 400"""
    # mock 掉真实检索（本地无 Milvus，只测鉴权与契约）
    monkeypatch.setattr("yuanai_core.rag.search_knowledge",
                        lambda query, top_k=10, user_id=None, **kw: f"hit:{query}:{user_id}")

    # 坏 secret
    r = client.post("/api/v1/agent/knowledge/search", headers=_hdrs(env, secret="wrong"),
                    json={"query": "x", "user_id": env["uid"]})
    assert r.status_code == 401

    # 未绑定设备
    from db.session import AgentDevice
    sess = db.Session()
    try:
        unbound = AgentDevice(install_code="KB-U-" + uuid.uuid4().hex[:8],
                              agent_secret="kb-u-" + uuid.uuid4().hex[:8],
                              machine_name="kb-u", user_id=None)
        sess.add(unbound)
        sess.commit()
        unbound_id = unbound.id
    finally:
        sess.close()
    try:
        r = client.post("/api/v1/agent/knowledge/search",
                        headers=_hdrs(env, agent_id=unbound_id, secret=unbound.agent_secret),
                        json={"query": "x"})
        assert r.status_code == 403
    finally:
        sess = db.Session()
        try:
            sess.query(AgentDevice).filter_by(id=unbound_id).delete()
            sess.commit()
        finally:
            sess.close()

    # user_id 与设备绑定不符
    r = client.post("/api/v1/agent/knowledge/search", headers=_hdrs(env),
                    json={"query": "x", "user_id": env["uid"] + 999})
    assert r.status_code == 403

    # 缺 query 400
    r = client.post("/api/v1/agent/knowledge/search", headers=_hdrs(env), json={})
    assert r.status_code == 400

    # 正常：检索在云端按设备绑定用户执行
    r = client.post("/api/v1/agent/knowledge/search", headers=_hdrs(env),
                    json={"query": "销售", "top_k": 3})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True and data["text"] == f"hit:销售:{env['uid']}"


# ---------------- knowledge_tool 双路径 ----------------

def test_tool_remote_path_uses_http(monkeypatch):
    """部署 Agent（is_remote_agent=True）→ agent_http 到 /knowledge/search"""
    from yuanai_core.tools import knowledge_tool as kt

    calls = []
    monkeypatch.setattr("yuanai_core.tools._agent_remote.is_remote_agent", lambda: True)
    monkeypatch.setattr("yuanai_core.tools._agent_remote.agent_http",
                        lambda path, method, payload, timeout=15: calls.append((path, method, payload, timeout)) or
                        {"ok": True, "text": "[知识源] 命中内容"})

    out = kt.retrieve_knowledge.invoke({"query": "数据规范"})
    assert out == "[知识源] 命中内容"
    assert calls[0][0] == "/knowledge/search" and calls[0][1] == "POST"
    assert calls[0][2]["query"] == "数据规范" and calls[0][2]["top_k"] == 5

    # 空 query：远程路径快速返回，不碰本地 Milvus
    out = kt.retrieve_knowledge.invoke({"query": "  "})
    assert out == "请提供搜索关键词"
    assert len(calls) == 1  # 未发起新请求

    # 云端失败透传
    monkeypatch.setattr("yuanai_core.tools._agent_remote.agent_http",
                        lambda *a, **kw: {"ok": False, "detail": "HTTP 502"})
    out = kt.retrieve_knowledge.invoke({"query": "x"})
    assert "502" in out


def test_tool_direct_path_uses_local_rag(monkeypatch):
    """云端进程/本地联调（is_remote_agent=False）→ 直连本机 rag.search_knowledge"""
    from yuanai_core.tools import knowledge_tool as kt

    seen = {}
    monkeypatch.setattr("yuanai_core.tools._agent_remote.is_remote_agent", lambda: False)
    monkeypatch.setattr("yuanai_core.rag.search_knowledge",
                        lambda query, user_id=None, **kw: seen.update(query=query, user_id=user_id) or "直连结果")
    out = kt.retrieve_knowledge.invoke({"query": "规范"})
    assert out == "直连结果"
    assert seen["query"] == "规范"


# ---------------- rag 快速失败 ----------------

def test_get_db_fail_cooldown(monkeypatch):
    """连接失败后冷却期内快速返回 None，不再每轮重试连接"""
    import yuanai_core.rag as rag

    monkeypatch.setattr(rag, "_db", None)
    monkeypatch.setattr(rag, "_db_fail_until", time.time() + 60)
    monkeypatch.setattr(rag, "MilvusClient", lambda **kw: (_ for _ in ()).throw(
        AssertionError("冷却期内不应重连")))
    assert rag._get_db() is None
    # 冷却期结束后允许重连
    monkeypatch.setattr(rag, "_db_fail_until", 0.0)
    monkeypatch.setattr(rag, "MilvusClient", lambda **kw: (_ for _ in ()).throw(
        RuntimeError("连接失败模拟")))
    assert rag._get_db() is None
    assert rag._db_fail_until > time.time()  # 失败重新进入冷却


if __name__ == "__main__":
    print("测试入口：pytest test/test_knowledge_search_api.py -v")
