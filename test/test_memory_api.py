# -*- coding: utf-8 -*-
"""记忆机制 API 测试 — GET/PUT /auth/memory 往返与超限（P0 透明可编辑）

端点测试需要 MySQL（不可用则跳过）。运行：pytest test/test_memory_api.py -v
"""
import sys
import os

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
def mem_user(db):
    """自建测试用户（清理残留）"""
    from db.session import User

    sess = db.Session()
    try:
        old = sess.query(User).filter_by(username="__mem_test__").first()
        if old:
            sess.delete(old)
            sess.commit()
    finally:
        sess.close()

    r = db.register_user("__mem_test__", "test123")
    assert "error" not in r, r
    yield r
    sess = db.Session()
    try:
        u = sess.query(User).filter_by(id=r["id"]).first()
        if u:
            sess.delete(u)
            sess.commit()
    finally:
        sess.close()


@pytest.fixture(scope="module")
def mem_headers(mem_user):
    from api.v1.auth.utils import create_token
    return {"Authorization": f"Bearer {create_token(mem_user['id'], 'user')}"}


def test_memory_roundtrip(client, mem_headers):
    # 未登录 401
    assert client.get("/api/v1/auth/memory").status_code == 401
    assert client.put("/api/v1/auth/memory", json={"memory": "x"}).status_code == 401

    # 初始为空
    r = client.get("/api/v1/auth/memory", headers=mem_headers)
    assert r.status_code == 200
    assert r.json()["memory"] == ""
    assert r.json()["count"] == 0
    assert r.json()["max_items"] == 100

    # 写入（含 \r\n 与空行 → 归一化）
    r = client.put("/api/v1/auth/memory", headers=mem_headers,
                   json={"memory": "用户是数据分析师\r\n\r\n  用户怕辣  \n\n"})
    assert r.status_code == 200, r.text
    assert r.json()["memory"] == "用户是数据分析师\n用户怕辣"
    assert r.json()["count"] == 2

    # 读回一致
    r = client.get("/api/v1/auth/memory", headers=mem_headers)
    assert r.json()["memory"] == "用户是数据分析师\n用户怕辣"
    assert r.json()["count"] == 2

    # 清空
    r = client.put("/api/v1/auth/memory", headers=mem_headers, json={"memory": ""})
    assert r.status_code == 200
    assert r.json()["memory"] == ""


def test_memory_over_limit_rejected(client, mem_headers):
    # 超条数 → 400（拒绝而非截断）
    many = "\n".join(f"事实{i}" for i in range(101))
    r = client.put("/api/v1/auth/memory", headers=mem_headers, json={"memory": many})
    assert r.status_code == 400
    assert "精简" in r.json()["detail"]

    # 超字数 → 400
    long_line = "字" * 2100
    r = client.put("/api/v1/auth/memory", headers=mem_headers, json={"memory": long_line})
    assert r.status_code == 400
    assert "精简" in r.json()["detail"]

    # 恰好上限内 → 200
    ok = "\n".join(f"事实{i}" for i in range(100))
    r = client.put("/api/v1/auth/memory", headers=mem_headers, json={"memory": ok})
    assert r.status_code == 200
    # 还原
    client.put("/api/v1/auth/memory", headers=mem_headers, json={"memory": ""})


if __name__ == "__main__":
    print("测试入口：pytest test/test_memory_api.py -v")


# ===================== P1：反馈三态（liked/disliked 互斥） =====================

def _make_session(client, mem_headers):
    """建一个会话（owner=测试用户），返回 session_id"""
    r = client.post("/api/v1/chat/session/new", headers=mem_headers, json={"title": "mem-fb-test"})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def test_feedback_three_state(client, mem_headers):
    sid = _make_session(client, mem_headers)

    # 点赞
    r = client.post("/api/v1/chat/feedback", headers=mem_headers,
                    json={"session_id": sid, "message_index": 3, "liked": True})
    assert r.status_code == 200 and r.json()["liked"] is True
    got = client.get(f"/api/v1/chat/feedback?session_id={sid}", headers=mem_headers).json()
    assert got["3"] == {"liked": True, "disliked": False}

    # 再点踩 → 互斥翻转
    r = client.post("/api/v1/chat/feedback", headers=mem_headers,
                    json={"session_id": sid, "message_index": 3, "disliked": True})
    assert r.status_code == 200 and r.json()["disliked"] is True
    got = client.get(f"/api/v1/chat/feedback?session_id={sid}", headers=mem_headers).json()
    assert got["3"] == {"liked": False, "disliked": True}

    # 再点赞取消（liked=False 且 disliked=False）→ 两态皆无，GET 不含该下标
    r = client.post("/api/v1/chat/feedback", headers=mem_headers,
                    json={"session_id": sid, "message_index": 3, "liked": False})
    assert r.status_code == 200
    got = client.get(f"/api/v1/chat/feedback?session_id={sid}", headers=mem_headers).json()
    assert "3" not in got

    # 旧客户端只发 liked=true → 行为不变
    r = client.post("/api/v1/chat/feedback", headers=mem_headers,
                    json={"session_id": sid, "message_index": 1, "liked": True})
    assert r.status_code == 200
    got = client.get(f"/api/v1/chat/feedback?session_id={sid}", headers=mem_headers).json()
    assert got["1"] == {"liked": True, "disliked": False}


def test_feedback_foreign_session_403(client, mem_headers):
    """越权：他人会话的反馈 → 403"""
    from db.session import get_db
    db = get_db()
    other = db.register_user("__mem_fb_other__", "test123")
    try:
        from api.v1.auth.utils import create_token
        h2 = {"Authorization": f"Bearer {create_token(other['id'], 'user')}"}
        sid2 = _make_session(client, h2)
        r = client.post("/api/v1/chat/feedback", headers=mem_headers,
                        json={"session_id": sid2, "message_index": 0, "liked": True})
        assert r.status_code in (403, 404), r.status_code
    finally:
        from db.session import User
        sess = db.Session()
        try:
            u = sess.query(User).filter_by(id=other["id"]).first()
            if u:
                sess.delete(u)
                sess.commit()
        finally:
            sess.close()


# ===================== P1：折叠游标表方法 =====================

def test_session_memory_state_upsert_max(db):
    """游标 upsert 只增不减（并发防回退）"""
    sid = "mem_state_test_sid"
    try:
        assert db.get_session_memory_state(sid) is None
        db.upsert_session_memory_state(sid, 1, 10)
        assert db.get_session_memory_state(sid)["folded_count"] == 10
        db.upsert_session_memory_state(sid, 1, 8)   # 旧值回退 → 保持 10
        assert db.get_session_memory_state(sid)["folded_count"] == 10
        db.upsert_session_memory_state(sid, 1, 15)  # 前进 → 15
        assert db.get_session_memory_state(sid)["folded_count"] == 15
    finally:
        sess = db.Session()
        try:
            from db.session import SessionMemoryState
            sess.query(SessionMemoryState).filter_by(session_id=sid).delete()
            sess.commit()
        finally:
            sess.close()


def test_merge_user_memory_dedup(db):
    """合并去重：完全重复与「旧行包含新行」都跳过；只追加不重排"""
    uid = db.register_user("__mem_merge_test__", "test123")["id"]
    try:
        db.update_user_memory(uid, "用户怕辣\n在做跨境电商项目")
        # 「用户怕辣」完全重复跳过；「跨境电商」⊂ 旧行「在做跨境电商项目」跳过；
        # 只有「喜欢用 pandas」是新增
        r = db.merge_user_memory(uid, ["用户怕辣", "喜欢用 pandas", "跨境电商"], 100, 2000)
        assert r["added"] == 1, r
        mem = db.get_user_memory(uid)
        assert mem == "用户怕辣\n在做跨境电商项目\n喜欢用 pandas"  # 原顺序不变，新行追加
    finally:
        from db.session import User
        sess = db.Session()
        try:
            u = sess.query(User).filter_by(id=uid).first()
            if u:
                sess.delete(u)
                sess.commit()
        finally:
            sess.close()
