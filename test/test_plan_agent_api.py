# -*- coding: utf-8 -*-
"""计划同步 Agent 侧 API 测试 — 设备凭据鉴权 / pull→progress→done 全链 / 节流 / 幂等（需 MySQL）

运行：pytest test/test_plan_agent_api.py -v
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
def env(db):
    """用户 + 绑定设备（secret 已知）"""
    from db.session import AgentDevice, User
    uid = db.register_user("__plan_agent__", "test123")["id"]
    secret = "plan-secret-" + uuid.uuid4().hex[:12]
    dev = AgentDevice(install_code="PLAN-" + uuid.uuid4().hex[:8], agent_secret=secret,
                      machine_name="plan-test", user_id=uid)
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


def _mk(client, h, steps=None):
    return client.post("/api/v1/agent/plan/create", headers=h, json={
        "title": "Agent 计划", "goal": "先抓再分析",
        "steps": steps or [
            {"skill": "collection", "desc": "抓取示例数据", "params": {"url": "https://example.com"}},
            {"skill": "analysis", "desc": "描述性统计分析", "params": {"dataset_id": 1}},
        ]}).json()["plan_id"]


def _exec(client, h, pid):
    return client.post("/api/v1/agent/plan/execute", headers=h, json={"plan_id": pid})


# ---------------- 鉴权矩阵 ----------------

def test_agent_auth_matrix(client, env, db):
    assert client.post("/api/v1/agent/plan/pull", json={}).status_code == 401
    r = client.post("/api/v1/agent/plan/pull", json={},
                    headers=_hdrs(env, secret="wrong"))
    assert r.status_code == 401
    # 未绑定设备 → 403
    from db.session import AgentDevice
    sess = db.Session()
    try:
        unbound = AgentDevice(install_code="PLAN-" + uuid.uuid4().hex[:8],
                              agent_secret="unbound-x", machine_name="x")
        sess.add(unbound)
        sess.commit()
        unbound_id = unbound.id
    finally:
        sess.close()
    try:
        r = client.post("/api/v1/agent/plan/pull", json={},
                        headers=_hdrs(env, agent_id=unbound_id, secret="unbound-x"))
        assert r.status_code == 403 and "未绑定" in r.json()["detail"]
    finally:
        sess = db.Session()
        try:
            sess.query(AgentDevice).filter_by(id=unbound_id).delete()
            sess.commit()
        finally:
            sess.close()


# ---------------- 全链 ----------------

def test_pull_progress_done_chain(client, env, db):
    pid = _mk(client, _hdrs(env))
    assert _exec(client, _hdrs(env), pid).json()["ok"] is True

    # pull 认领第一步
    r = client.post("/api/v1/agent/plan/pull", json={}, headers=_hdrs(env)).json()
    assert not r["empty"] and r["step"]["step_no"] == 1 and r["step"]["status"] == "running"
    sid1 = r["step"]["id"]
    # 第二步不可抢（同计划串行）
    r2 = client.post("/api/v1/agent/plan/pull", json={}, headers=_hdrs(env)).json()
    assert r2["empty"] is True

    # 进度
    p = client.post("/api/v1/agent/plan/progress", headers=_hdrs(env),
                    json={"step_id": sid1, "current": 1, "total": 2, "message": "抓取中"})
    assert p.status_code == 200 and p.json()["throttled"] is False
    # 节流：同秒第二次 → throttled
    p2 = client.post("/api/v1/agent/plan/progress", headers=_hdrs(env),
                     json={"step_id": sid1, "current": 1, "total": 2, "message": "抓取中"})
    assert p2.json()["throttled"] is True

    # 完成第一步
    d = client.post("/api/v1/agent/plan/step-done", headers=_hdrs(env), json={
        "step_id": sid1, "summary": "抓到 100 行", "script": "网页采集脚本",
        "result_json": {"text": "抓到 100 行数据", "blocks": {"kpi": [{"label": "行数", "value": 100}]}}})
    assert d.status_code == 200 and d.json()["ok"] is True
    # 幂等
    d2 = client.post("/api/v1/agent/plan/step-done", headers=_hdrs(env), json={
        "step_id": sid1, "summary": "x", "result_json": {}})
    assert d2.json()["already"] is True

    # 第二步可认领，带前序摘要
    r3 = client.post("/api/v1/agent/plan/pull", json={}, headers=_hdrs(env)).json()
    assert not r3["empty"] and r3["step"]["step_no"] == 2
    assert any("抓到 100 行" in prev["summary"] for prev in r3["prev"])
    # 完成第二步 → 计划 done
    client.post("/api/v1/agent/plan/step-done", headers=_hdrs(env), json={
        "step_id": r3["step"]["id"], "summary": "完成", "result_json": {}})
    plan = db.get_plan(pid, env["uid"])
    assert plan["status"] == "done" and plan["done_steps"] == 2 and plan["progress"] == 100
    runs = db.list_plan_runs(pid, env["uid"])
    events = [x["event"] for x in runs]
    assert "plan_done" in events and "claimed" in events and "step_done" in events


# ---------------- 失败重试 ----------------

def test_step_failed_retry_once_then_failed(client, env, db):
    pid = _mk(client, _hdrs(env), steps=[
        {"skill": "analysis", "desc": "一步计划", "params": {}}])
    _exec(client, _hdrs(env), pid)
    r = client.post("/api/v1/agent/plan/pull", json={}, headers=_hdrs(env)).json()
    sid = r["step"]["id"]

    # 第一次失败 retryable → 回 pending 自动重试
    f = client.post("/api/v1/agent/plan/step-failed", headers=_hdrs(env),
                    json={"step_id": sid, "error": "网络超时", "retryable": True})
    assert f.json()["retry"] is True
    s = db.get_plan_step(sid, env["uid"])
    assert s["status"] == "pending" and s["attempt"] == 1

    # 重新认领（attempt→2）再失败 retryable → 超过 2 次直接 failed
    r2 = client.post("/api/v1/agent/plan/pull", json={}, headers=_hdrs(env)).json()
    assert not r2["empty"] and r2["step"]["attempt"] == 2
    f2 = client.post("/api/v1/agent/plan/step-failed", headers=_hdrs(env),
                     json={"step_id": sid, "error": "还是超时", "retryable": True})
    assert f2.json()["retry"] is False
    assert db.get_plan_step(sid, env["uid"])["status"] == "failed"
    assert db.get_plan(pid, env["uid"])["status"] == "failed"


def test_foreign_step_id_404(client, env, db):
    """伪造他人 step_id → 404（user_id 冗余校验）"""
    from db.session import User
    other = db.register_user("__plan_other_agent__", "test123")["id"]
    try:
        pid = db.create_plan(other, "他人计划", "x", [{"skill": "analysis", "desc": "x"}])["plan_id"]
        sid = db.get_plan_steps(pid, other)[0]["id"]
        r = client.post("/api/v1/agent/plan/progress", headers=_hdrs(env),
                        json={"step_id": sid, "current": 1, "total": 2, "message": "x"})
        assert r.status_code == 404
        db.delete_plan_cascade(pid, other)
    finally:
        sess = db.Session()
        try:
            u = sess.query(User).filter_by(id=other).first()
            if u:
                sess.delete(u)
            sess.commit()
        finally:
            sess.close()


if __name__ == "__main__":
    print("测试入口：pytest test/test_plan_agent_api.py -v")
