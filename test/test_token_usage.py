# -*- coding: utf-8 -*-
"""Token 用量统计测试 — 回调记账 / 缓冲冲刷 / 聚合查询 / admin 端点

运行：pytest test/test_token_usage.py -v
聚合与端点部分需要 MySQL（不可用则跳过），回调纯逻辑离线可跑。
"""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')


# ---------------- 回调记账（离线） ----------------

def test_handler_extracts_usage_and_records(monkeypatch):
    from yuanai_core import usage as u
    from yuanai_core.rag import current_user_id

    recorded = []
    monkeypatch.setattr(u, "record_usage",
                        lambda *a, **kw: recorded.append((a, kw)))

    class FakeResponse:
        usage_metadata = {"input_tokens": 120, "output_tokens": 30}
        response_metadata = {}

    tok = current_user_id.set(42)
    try:
        u.UsageTrackingHandler().on_llm_end(
            FakeResponse(), invocation_params={"model": "deepseek-v4-pro"})
    finally:
        current_user_id.reset(tok)

    assert recorded == [((42, "deepseek-v4-pro", "chat", 120, 30),
                         {"source": "cloud"})]


def test_handler_no_usage_skips(monkeypatch):
    from yuanai_core import usage as u

    recorded = []
    monkeypatch.setattr(u, "record_usage", lambda *a, **kw: recorded.append(a))

    class FakeResponse:
        usage_metadata = None
        response_metadata = {}

    u.UsageTrackingHandler().on_llm_end(FakeResponse(), invocation_params={})
    assert recorded == []


def test_handler_never_raises(monkeypatch):
    from yuanai_core import usage as u

    monkeypatch.setattr(u, "current_user_id", None)  # 触发内部异常路径
    u.UsageTrackingHandler().on_llm_end(None, invocation_params=None)  # 不抛即过


# ---------------- 缓冲与落库（MySQL skip） ----------------

def _db_or_skip():
    try:
        from db.session import get_db
        return get_db()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


@pytest.fixture(scope="module")
def db():
    return _db_or_skip()


def test_usage_rows_roundtrip_and_query(db):
    """落库 → 聚合查询（day/model/user 三种口径）"""
    from yuanai_core.usage import record_usage, flush_now

    uid = 999990
    db.add_token_usage_rows([
        {"user_id": uid, "model": "deepseek-v4-pro", "purpose": "chat",
         "prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150,
         "source": "cloud"},
        {"user_id": uid, "model": "doubao-seed-2-0-lite-260215", "purpose": "chat",
         "prompt_tokens": 200, "completion_tokens": 20, "total_tokens": 220,
         "source": "cloud"},
        {"user_id": uid + 1, "model": "deepseek-v4-pro", "purpose": "chat",
         "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
         "source": "agent"},
    ])
    try:
        # 按模型聚合
        by_model = {r["key"]: r for r in db.query_token_usage(days=7, group_by="model")}
        assert by_model["deepseek-v4-pro"]["total_tokens"] == 165
        assert by_model["doubao-seed-2-0-lite-260215"]["total_tokens"] == 220

        # 按用户聚合
        by_user = {r["key"]: r for r in db.query_token_usage(days=7, group_by="user")}
        assert by_user[str(uid)]["total_tokens"] == 370

        # 按天聚合（非空 + 字段齐全）
        by_day = db.query_token_usage(days=7, group_by="day")
        assert by_day and by_day[0]["calls"] >= 3
    finally:
        # 清理
        sess = db.Session()
        try:
            from db.session import TokenUsage
            sess.query(TokenUsage).filter(TokenUsage.user_id.in_([uid, uid + 1])).delete()
            sess.commit()
        finally:
            sess.close()


def test_usage_admin_endpoint(client):
    """admin 端点：未登录 401 / group_by 校验 400 / 正常返回结构与 totals"""
    r = client.get("/api/v1/admin/token-usage")
    assert r.status_code == 401

    from db.session import get_db, User
    from api.v1.auth.utils import create_token
    db = get_db()
    db.register_user("__usage_admin__", "test123", role="admin")
    sess = db.Session()
    try:
        uid = sess.query(User).filter_by(username="__usage_admin__").first().id
    finally:
        sess.close()
    h = {"Authorization": f"Bearer {create_token(uid, 'admin')}"}
    try:
        assert client.get("/api/v1/admin/token-usage?group_by=bad", headers=h).status_code == 400
        r = client.get("/api/v1/admin/token-usage?days=7&group_by=model", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert "rows" in data and "totals" in data
        assert set(data["totals"]) >= {"total_tokens", "calls"}
    finally:
        sess = db.Session()
        try:
            u = sess.query(User).filter_by(id=uid).first()
            if u:
                sess.delete(u)
                sess.commit()
        finally:
            sess.close()


if __name__ == "__main__":
    print("测试入口：pytest test/test_token_usage.py -v")
