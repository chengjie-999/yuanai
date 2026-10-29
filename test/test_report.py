"""
C7 举报工单测试（2026-10-29，生成式AI服务管理暂行办法第 15 条投诉举报机制）

覆盖：DB 层增/查/处理、用户举报端点（归属校验/参数校验）、
管理员工单列表与处理端点（require_admin）。
"""
import pytest


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
def admin_jwt(db):
    """自建 admin 测试用户 → JWT（端点 require_admin 用）"""
    from db.session import User
    from api.v1.auth.utils import create_token

    sess = db.Session()
    try:
        old = sess.query(User).filter_by(username="__report_admin__").first()
        if old:
            sess.delete(old)
            sess.commit()
    finally:
        sess.close()

    r = db.register_user("__report_admin__", "test1234", role="admin")
    assert "error" not in r, r
    yield create_token(r["id"], "admin")
    sess = db.Session()
    try:
        u = sess.query(User).filter_by(id=r["id"]).first()
        if u:
            sess.delete(u)
            sess.commit()
    finally:
        sess.close()


def _cleanup_reports(db, session_id: str):
    from db.session import AIReport
    sess = db.Session()
    try:
        sess.query(AIReport).filter_by(session_id=session_id).delete()
        sess.commit()
    finally:
        sess.close()


class TestReportDb:
    """DB 层：工单落库/列表筛选/处理"""

    def test_add_and_list_report(self, db):
        rid = db.add_report(99999902, "sess-report-db", 2, "虚假信息", "被举报内容预览")
        try:
            assert isinstance(rid, int) and rid > 0
            rows = db.list_reports("pending")
            assert any(r["id"] == rid and r["reason"] == "虚假信息"
                       and r["status"] == "pending" for r in rows)
            # 状态筛选：pending 命中，handled 不命中
            assert all(r["status"] == "pending" for r in rows)
        finally:
            _cleanup_reports(db, "sess-report-db")

    def test_handle_report_and_404(self, db):
        rid = db.add_report(99999902, "sess-report-db2", 0, "有害内容", "x")
        try:
            assert db.handle_report(rid, "已核实处理") is True
            rows = db.list_reports("handled")
            hit = [r for r in rows if r["id"] == rid]
            assert hit and hit[0]["handler_note"] == "已核实处理"
            assert hit[0]["handled_at"]  # 处理时间已写
            # 不存在的工单 → False（端点映射 404）
            assert db.handle_report(999999999, "x") is False
        finally:
            _cleanup_reports(db, "sess-report-db2")


class TestReportApi:
    """API 层：举报提交 + 管理员处理"""

    def test_report_own_session(self, client, auth_headers, db):
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        create = client.post("/api/v1/chat/session/new", json={"title": "举报测试"}, headers=auth_headers)
        assert create.status_code == 200
        sid = create.json()["session_id"]
        try:
            client.post("/api/v1/chat/save", json={
                "session_id": sid,
                "messages": [{"role": "user", "content": "你好"},
                             {"role": "assistant", "content": "这是一条违规回复"}],
            }, headers=auth_headers)
            resp = client.post("/api/v1/chat/report", json={
                "session_id": sid, "message_index": 1, "reason": "违法违规内容：测试",
            }, headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True and data["report_id"] > 0
            # 工单已落库，内容预览 = 被举报消息内容（META 剥壳后）
            rows = db.list_reports("pending")
            hit = [r for r in rows if r["id"] == data["report_id"]]
            assert hit and "违规回复" in hit[0]["content_preview"]
        finally:
            _cleanup_reports(db, sid)

    def test_report_other_users_session_forbidden(self, client, auth_headers, db):
        """越权举报：会话属于他人 → 403（IDOR 防护）"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        # 第二用户建会话
        db.register_user("__report_user2__", "test1234")
        login = client.post("/api/v1/auth/login", json={
            "username": "__report_user2__", "password": "test1234"})
        assert login.status_code == 200
        h2 = {"Authorization": f"Bearer {login.json()['token']}"}
        create = client.post("/api/v1/chat/session/new", json={"title": "他人会话"}, headers=h2)
        assert create.status_code == 200
        sid = create.json()["session_id"]
        try:
            resp = client.post("/api/v1/chat/report", json={
                "session_id": sid, "message_index": 0, "reason": "越权测试",
            }, headers=auth_headers)
            assert resp.status_code == 403
        finally:
            _cleanup_reports(db, sid)

    def test_report_missing_fields(self, client, auth_headers):
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        resp = client.post("/api/v1/chat/report", json={
            "session_id": "x", "reason": "",
        }, headers=auth_headers)
        assert resp.status_code == 422  # reason 最短 1 字符

    def test_admin_list_and_handle(self, client, auth_headers, db, admin_jwt):
        """管理员列表 + 处理闭环；普通用户 403"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        # 普通用户不可访问
        assert client.get("/api/v1/admin/reports", headers=auth_headers).status_code == 403
        # 造一条工单
        rid = db.add_report(99999902, "sess-report-api", 0, "虚假信息", "预览")
        try:
            ah = {"Authorization": f"Bearer {admin_jwt}"}
            resp = client.get("/api/v1/admin/reports", headers=ah)
            assert resp.status_code == 200
            assert any(r["id"] == rid for r in resp.json())
            # 状态筛选
            resp_p = client.get("/api/v1/admin/reports?status=pending", headers=ah)
            assert any(r["id"] == rid for r in resp_p.json())
            assert not any(r["id"] == rid for r in client.get(
                "/api/v1/admin/reports?status=handled", headers=ah).json())
            # 处理
            resp = client.post(f"/api/v1/admin/reports/{rid}/handle",
                               json={"note": "已核实下架"}, headers=ah)
            assert resp.status_code == 200
            # 处理不存在的工单 → 404
            assert client.post("/api/v1/admin/reports/999999999/handle",
                               json={"note": "x"}, headers=ah).status_code == 404
            rows = db.list_reports("handled")
            hit = [r for r in rows if r["id"] == rid]
            assert hit and hit[0]["handler_note"] == "已核实下架"
        finally:
            _cleanup_reports(db, "sess-report-api")
