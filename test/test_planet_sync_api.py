# -*- coding: utf-8 -*-
"""vault 同步 API 测试 — 鉴权 401/403 矩阵 + pull/push 往返（幂等 upsert / 删除）

需要 MySQL（不可用则跳过）。运行：pytest test/test_planet_sync_api.py -v
"""
import sys
import os
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
def sync_env(db):
    """自建用户 + 绑定设备（secret 已知），模块结束清理"""
    from db.session import AgentDevice

    uid = db.register_user("__sync_test__", "test123")["id"]
    secret = "sync-secret-" + uuid.uuid4().hex[:12]
    dev = AgentDevice(install_code="SYNC-" + uuid.uuid4().hex[:8], agent_secret=secret,
                      machine_name="sync-test", user_id=uid)
    sess = db.Session()
    try:
        sess.add(dev)
        sess.commit()
        dev_id = dev.id
    finally:
        sess.close()

    yield {"uid": uid, "agent_id": dev_id, "secret": secret}

    # 清理
    from db.session import User
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


# ---------------- 鉴权矩阵 ----------------

def test_sync_auth_matrix(client, sync_env, db):
    # 无凭据 → 401
    assert client.get("/api/v1/agent/planet/pull/index").status_code == 401
    # 坏 secret → 401
    assert client.get("/api/v1/agent/planet/pull/index",
                      headers=_hdrs(sync_env, secret="wrong")).status_code == 401
    # 未绑定账号的设备 → 403
    from db.session import AgentDevice
    sess = db.Session()
    try:
        unbound = AgentDevice(install_code="SYNC-" + uuid.uuid4().hex[:8],
                              agent_secret="unbound-secret", machine_name="x")
        sess.add(unbound)
        sess.commit()
        unbound_id = unbound.id
    finally:
        sess.close()
    try:
        r = client.get("/api/v1/agent/planet/pull/index",
                       headers=_hdrs(sync_env, agent_id=unbound_id, secret="unbound-secret"))
        assert r.status_code == 403
        assert "未绑定" in r.json()["detail"]
    finally:
        sess = db.Session()
        try:
            sess.query(AgentDevice).filter_by(id=unbound_id).delete()
            sess.commit()
        finally:
            sess.close()


# ---------------- pull / push 往返 ----------------

def test_pull_empty_and_push_roundtrip(client, sync_env, db):
    # 初始索引为空
    r = client.get("/api/v1/agent/planet/pull/index", headers=_hdrs(sync_env))
    assert r.status_code == 200
    assert r.json()["notes"] == []

    # push upsert（新笔记，map_id=0 → 按星球收件箱新建）
    r = client.post("/api/v1/agent/planet/push/upsert", headers=_hdrs(sync_env),
                    json={"planet": "Obsidian同步测试", "map_id": 0,
                          "title": "我的 vault 笔记", "content": "# 标题\n正文内容"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True
    nid = body["id"]
    assert len(body["content_hash"]) == 64

    # 再 push 同一 map_id=0 → 新建第二行（自由笔记无 map 定位）——改用 map_id 定位验证幂等
    r2 = client.post("/api/v1/agent/planet/push/upsert", headers=_hdrs(sync_env),
                     json={"planet": "Obsidian同步测试", "map_id": 777,
                           "title": "带导图锚点的笔记", "content": "v1"})
    assert r2.status_code == 200 and r2.json()["created"] is True
    mid_nid = r2.json()["id"]

    r3 = client.post("/api/v1/agent/planet/push/upsert", headers=_hdrs(sync_env),
                     json={"planet": "另一个星球", "map_id": 777,
                           "title": "改标题了", "content": "v2"})
    assert r3.status_code == 200
    assert r3.json()["created"] is False          # 按 map_id 覆盖，不新建
    assert r3.json()["id"] == mid_nid
    assert r3.json()["content_hash"] != r2.json()["content_hash"]

    # pull index 能看到两条（新笔记 + map 笔记）
    r = client.get("/api/v1/agent/planet/pull/index", headers=_hdrs(sync_env))
    notes = r.json()["notes"]
    ids = {n["id"] for n in notes}
    assert nid in ids and mid_nid in ids
    # map 笔记的哈希是 v2 的
    mid_note = next(n for n in notes if n["id"] == mid_nid)
    assert mid_note["title"] == "改标题了"
    assert mid_note["content_hash"] == r3.json()["content_hash"]

    # pull content 批量
    r = client.get(f"/api/v1/agent/planet/pull/content?ids={nid},{mid_nid}",
                   headers=_hdrs(sync_env))
    assert r.status_code == 200
    contents = {n["id"]: n["content"] for n in r.json()["notes"]}
    assert contents[mid_nid] == "v2"

    # 越界 ids → 400
    assert client.get("/api/v1/agent/planet/pull/content?ids=abc",
                      headers=_hdrs(sync_env)).status_code == 400

    # push delete：删 map 笔记；再删一次 → 404
    r = client.post("/api/v1/agent/planet/push/delete", headers=_hdrs(sync_env),
                    json={"nid": mid_nid})
    assert r.status_code == 200
    r = client.post("/api/v1/agent/planet/push/delete", headers=_hdrs(sync_env),
                    json={"nid": mid_nid})
    assert r.status_code == 404

    # 清理残留（用户/设备在 fixture teardown 一并清）
    from api.v1.planet import store
    db.delete_note(nid, sync_env["uid"])
    for p in db.list_planets(sync_env["uid"]):
        store.delete_planet_cascade(sync_env["uid"], p["id"])


if __name__ == "__main__":
    print("测试入口：pytest test/test_planet_sync_api.py -v")
