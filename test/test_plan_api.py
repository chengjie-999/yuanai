# -*- coding: utf-8 -*-
"""计划闭环用户侧 API 测试 — JWT 鉴权/CRUD/状态机/越权/看门狗（需 MySQL）

运行：pytest test/test_plan_api.py -v
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
    """两个用户：owner（计划主人）+ other（越权测试）"""
    from db.session import User
    owner = db.register_user("__plan_owner__", "test123")["id"]
    other = db.register_user("__plan_other__", "test123")["id"]
    from api.v1.auth.utils import create_token
    yield {"owner": owner, "other": other,
           "h_owner": {"Authorization": f"Bearer {create_token(owner, 'user')}"},
           "h_other": {"Authorization": f"Bearer {create_token(other, 'user')}"}}
    sess = db.Session()
    try:
        for uid in (owner, other):
            u = sess.query(User).filter_by(id=uid).first()
            if u:
                sess.delete(u)
        sess.commit()
    finally:
        sess.close()


def _make_plan(client, h, title="测试计划"):
    r = client.post("/api/v1/plan", headers=h, json={
        "title": title, "goal": "先抓数据再分析",
        "steps": [
            {"skill": "collection", "desc": "抓取示例数据", "params": {"url": "https://example.com"}},
            {"skill": "analysis", "desc": "描述性统计分析", "params": {"dataset_id": 1}},
        ],
    })
    assert r.status_code == 200, r.text
    return r.json()["plan_id"]


def _exec(client, h, pid, step_ids=None):
    return client.post(f"/api/v1/plan/{pid}/execute", headers=h,
                       json={"step_ids": step_ids or []})


# ---------------- 鉴权与 CRUD ----------------

def test_plan_requires_login(client):
    assert client.get("/api/v1/plan/list").status_code == 401
    assert client.post("/api/v1/plan", json={"title": "x"}).status_code == 401
    assert client.get("/api/v1/plan/1").status_code == 401
    assert _exec(client, {}, 1).status_code == 401
    assert client.delete("/api/v1/plan/1").status_code == 401


def test_plan_create_list_detail_roundtrip(client, env):
    pid = _make_plan(client, env["h_owner"])
    r = client.get("/api/v1/plan/list", headers=env["h_owner"])
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()["plans"]]
    assert pid in ids and r.json()["plans"][0]["status"] == "draft"

    d = client.get(f"/api/v1/plan/{pid}", headers=env["h_owner"]).json()
    assert d["title"] == "测试计划" and len(d["steps"]) == 2
    assert d["steps"][0]["skill"] == "collection"
    assert d["steps"][0]["params"] == {"url": "https://example.com"}
    assert any(run["event"] == "created" for run in d["runs"])
    client.delete(f"/api/v1/plan/{pid}", headers=env["h_owner"])


def test_plan_invalid_steps_rejected(client, env):
    r = client.post("/api/v1/plan", headers=env["h_owner"], json={
        "title": "x", "goal": "", "steps": []})
    assert r.status_code == 400


def test_plan_foreign_access_404(client, env):
    pid = _make_plan(client, env["h_owner"])
    assert client.get(f"/api/v1/plan/{pid}", headers=env["h_other"]).status_code == 404
    assert _exec(client, env["h_other"], pid).status_code == 404
    assert client.delete(f"/api/v1/plan/{pid}", headers=env["h_other"]).status_code == 404
    client.delete(f"/api/v1/plan/{pid}", headers=env["h_owner"])


# ---------------- 状态机 ----------------

def test_plan_execute_queued_idempotent(client, env, db):
    pid = _make_plan(client, env["h_owner"])
    r = _exec(client, env["h_owner"], pid)
    assert r.status_code == 200 and r.json()["ok"] is True and r.json()["already"] is False
    d = client.get(f"/api/v1/plan/{pid}", headers=env["h_owner"]).json()
    assert d["status"] == "queued"
    # 幂等：重复 execute → already
    r2 = _exec(client, env["h_owner"], pid)
    assert r2.json()["already"] is True
    # 运行中不可删
    assert client.delete(f"/api/v1/plan/{pid}", headers=env["h_owner"]).status_code == 409
    # 清理：置 done 后删
    from db.session import Plan
    sess = db.Session()
    try:
        p = sess.query(Plan).filter_by(id=pid).first()
        p.status = "done"
        sess.commit()
    finally:
        sess.close()
    assert client.delete(f"/api/v1/plan/{pid}", headers=env["h_owner"]).status_code == 200


def test_plan_done_state_not_executable(client, env, db):
    pid = _make_plan(client, env["h_owner"])
    from db.session import Plan
    sess = db.Session()
    try:
        p = sess.query(Plan).filter_by(id=pid).first()
        p.status = "done"
        sess.commit()
    finally:
        sess.close()
    assert _exec(client, env["h_owner"], pid).status_code == 409
    client.delete(f"/api/v1/plan/{pid}", headers=env["h_owner"])


def test_plan_rerun_failed_steps(client, env, db):
    """failed 计划可重跑指定失败步 → 回 queued"""
    pid = _make_plan(client, env["h_owner"])
    step_ids = [s["id"] for s in db.get_plan_steps(pid)]
    db.update_plan_step(step_ids[0], env["owner"], status="failed", error="boom")
    db.update_plan(pid, env["owner"], status="failed", error="boom")
    r = _exec(client, env["h_owner"], pid, step_ids=[step_ids[0]])
    assert r.status_code == 200 and r.json()["already"] is False
    steps = db.get_plan_steps(pid, env["owner"])
    assert steps[0]["status"] == "pending" and steps[1]["status"] == "pending"
    d = client.get(f"/api/v1/plan/{pid}", headers=env["h_owner"]).json()
    assert d["status"] == "queued"
    # 运行中清理
    from db.session import Plan
    sess = db.Session()
    try:
        p = sess.query(Plan).filter_by(id=pid).first()
        p.status = "done"
        sess.commit()
    finally:
        sess.close()
    client.delete(f"/api/v1/plan/{pid}", headers=env["h_owner"])


# ---------------- 看门狗（计划级超时） ----------------

def test_plan_watchdog_timeout_failed(client, env, db):
    from datetime import datetime, timedelta
    pid = _make_plan(client, env["h_owner"])
    db.update_plan(pid, env["owner"], status="running")
    # bulk update 绕过 ORM onupdate，把 update_time 改旧
    sess = db.Session()
    try:
        from db.session import Plan
        sess.query(Plan).filter(Plan.id == pid).update(
            {"update_time": datetime.now() - timedelta(seconds=3700)},
            synchronize_session=False)
        sess.commit()
    finally:
        sess.close()
    d = client.get(f"/api/v1/plan/{pid}", headers=env["h_owner"]).json()
    assert d["status"] == "failed" and "超时" in d["error"]
    client.delete(f"/api/v1/plan/{pid}", headers=env["h_owner"])


# ---------------- 并发认领（CAS + 同计划串行） ----------------

def test_claim_cas_and_serial(client, env, db):
    """两个设备并发拉取：各自拿到不同计划的步骤；同计划内严格串行"""
    p1 = _make_plan(client, env["h_owner"], title="计划A")
    p2 = _make_plan(client, env["h_owner"], title="计划B")
    db.update_plan(p1, env["owner"], status="queued")
    db.update_plan(p2, env["owner"], status="queued")
    c1 = db.claim_next_plan_step(env["owner"], "dev-1")
    c2 = db.claim_next_plan_step(env["owner"], "dev-2")
    assert c1 and c2 and c1["plan"]["id"] != c2["plan"]["id"]  # 不抢同一步
    # dev-1 完成自己那步后，同计划下一步才可认领；其他计划不受阻
    db.update_plan_step(c1["step"]["id"], env["owner"], status="done")
    c3 = db.claim_next_plan_step(env["owner"], "dev-1")
    assert c3 and c3["plan"]["id"] == c1["plan"]["id"] and c3["step"]["step_no"] == 2
    # 清理
    from db.session import Plan
    sess = db.Session()
    try:
        for pid in (p1, p2):
            p = sess.query(Plan).filter_by(id=pid).first()
            p.status = "done"
        sess.commit()
    finally:
        sess.close()
    client.delete(f"/api/v1/plan/{p1}", headers=env["h_owner"])
    client.delete(f"/api/v1/plan/{p2}", headers=env["h_owner"])


if __name__ == "__main__":
    print("测试入口：pytest test/test_plan_api.py -v")


def test_plan_step_script_roundtrip(client, env, db):
    """R4：steps 带 script 落库并从详情/pull 读回"""
    r = client.post("/api/v1/plan", headers=env["h_owner"], json={
        "title": "脚本绑定计划", "goal": "x",
        "steps": [{"skill": "analysis", "script": "descriptive_stats",
                   "desc": "做统计", "params": {"dataset_id": 8}}],
    })
    assert r.status_code == 200, r.text
    pid = r.json()["plan_id"]
    d = client.get(f"/api/v1/plan/{pid}", headers=env["h_owner"]).json()
    assert d["steps"][0]["script"] == "descriptive_stats"
    steps = db.get_plan_steps(pid, env["owner"])
    assert steps[0]["script"] == "descriptive_stats"
    client.delete(f"/api/v1/plan/{pid}", headers=env["h_owner"])
