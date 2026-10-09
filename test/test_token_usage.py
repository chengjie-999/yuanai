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


# ===================== 文件管理 HTML 渲染预览 =====================

def test_file_html_preview_endpoint(client, db):
    """file-html：路径越权 400 / 沙箱头 / 未登录 401"""
    from api.v1.auth.utils import create_token

    db.register_user("__htmlprev_admin__", "test123", role="admin")
    from db.session import User
    sess = db.Session()
    try:
        uid = sess.query(User).filter_by(username="__htmlprev_admin__").first().id
    finally:
        sess.close()
    h = {"Authorization": f"Bearer {create_token(uid, 'admin')}"}
    try:
        # 未登录 401
        assert client.get("/api/v1/admin/file-html?path=cases%2Fx.html").status_code == 401
        # 越权路径 400
        assert client.get("/api/v1/admin/file-html?path=..%2F..%2Fetc%2Fpasswd", headers=h).status_code in (400, 404)
        # 非 html 文件 404
        assert client.get("/api/v1/admin/file-html?path=datasets%2Fnonexist.csv", headers=h).status_code == 404
    finally:
        sess = db.Session()
        try:
            u = sess.query(User).filter_by(id=uid).first()
            if u:
                sess.delete(u)
                sess.commit()
        finally:
            sess.close()


# ===================== 用户行为分析（访问埋点 uid 归因 + 分析端点） =====================

def test_visit_attribution(client, db):
    """埋点带登录态 → visit_log.user_id 关联；无登录态 → 0"""
    from api.v1.auth.utils import create_token

    r = client.post("/api/v1/stats/visit", json={"path": "/public-page"})
    assert r.status_code == 200

    db.register_user("__visit_attr__", "test123")
    from db.session import User
    sess = db.Session()
    try:
        uid = sess.query(User).filter_by(username="__visit_attr__").first().id
    finally:
        sess.close()
    h = {"Authorization": f"Bearer {create_token(uid, 'user')}"}
    r = client.post("/api/v1/stats/visit", json={"path": "/chat"}, headers=h)
    assert r.status_code == 200

    from db.session import VisitLog
    sess = db.Session()
    try:
        row = sess.query(VisitLog).filter_by(path="/chat").order_by(VisitLog.id.desc()).first()
        assert row.user_id == uid
        pub = sess.query(VisitLog).filter_by(path="/public-page").order_by(VisitLog.id.desc()).first()
        assert pub.user_id == 0
        # 清理
        sess.query(VisitLog).filter(VisitLog.path.in_(["/chat", "/public-page"])).delete()
        u = sess.query(User).filter_by(id=uid).first()
        if u:
            sess.delete(u)
        sess.commit()
    finally:
        sess.close()


def test_user_analytics_endpoint(client, db):
    """/admin/user-analytics：非 admin 拒绝；admin 返回指标体系结构"""
    from api.v1.auth.utils import create_token

    db.register_user("__ua_admin__", "test123", role="admin")
    db.register_user("__ua_normal__", "test123")
    from db.session import User
    sess = db.Session()
    try:
        admin_uid = sess.query(User).filter_by(username="__ua_admin__").first().id
        normal_uid = sess.query(User).filter_by(username="__ua_normal__").first().id
    finally:
        sess.close()

    h_admin = {"Authorization": f"Bearer {create_token(admin_uid, 'admin')}"}
    h_normal = {"Authorization": f"Bearer {create_token(normal_uid, 'user')}"}
    try:
        assert client.get("/api/v1/admin/user-analytics", headers=h_normal).status_code in (401, 403)
        r = client.get("/api/v1/admin/user-analytics?days=7", headers=h_admin)
        assert r.status_code == 200
        data = r.json()
        assert set(data) >= {"overview", "pages", "daily", "users", "segments"}
        assert set(data["overview"]) >= {"today", "period"}
        assert set(data["segments"]) >= {"high", "mid", "low", "churned"}
    finally:
        sess = db.Session()
        try:
            for name in ("__ua_admin__", "__ua_normal__"):
                u = sess.query(User).filter_by(username=name).first()
                if u:
                    sess.delete(u)
            sess.commit()
        finally:
            sess.close()
