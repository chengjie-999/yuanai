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
