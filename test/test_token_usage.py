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


# ===================== 文件管理 CRUD =====================

def test_file_crud_roundtrip(client, db):
    from api.v1.auth.utils import create_token
    import shutil as _shutil
    from utils.data_path import root_path as _rp

    # 清理上次失败运行的残留
    _residue = _shutil.rmtree
    for _res in ("__crud_test_dir__", "__crud_test_dir__/测试文件.txt", "__crud_test_dir__/改名后.txt"):
        _p = os.path.join(_rp(), "data", _res)
        if os.path.isdir(_p):
            _shutil.rmtree(_p, ignore_errors=True)
        elif os.path.isfile(_p):
            os.remove(_p)

    db.register_user("__filecrud_admin__", "test123", role="admin")
    from db.session import User
    sess = db.Session()
    try:
        uid = sess.query(User).filter_by(username="__filecrud_admin__").first().id
    finally:
        sess.close()
    h = {"Authorization": f"Bearer {create_token(uid, 'admin')}"}
    try:
        # 401
        assert client.post("/api/v1/admin/file/mkdir", json={"path": "", "name": "x"}).status_code == 401
        # 越权 400
        assert client.post("/api/v1/admin/file/mkdir", headers=h,
                           json={"path": "../..", "name": "x"}).status_code == 400
        # 新建目录 → 上传 → 重命名 → 删除（链路）
        r = client.post("/api/v1/admin/file/mkdir", headers=h,
                        json={"path": "", "name": "__crud_test_dir__"})
        assert r.status_code == 200, r.text
        # 同名 409
        assert client.post("/api/v1/admin/file/mkdir", headers=h,
                           json={"path": "", "name": "__crud_test_dir__"}).status_code == 409
        # 上传
        r = client.post("/api/v1/admin/file/upload?path=__crud_test_dir__", headers=h,
                        files={"file": ("测试文件.txt", b"hello crud", "text/plain")})
        assert r.status_code == 200, r.text
        # 重命名
        r = client.post("/api/v1/admin/file/rename", headers=h,
                        json={"path": "__crud_test_dir__/测试文件.txt", "name": "改名后.txt"})
        assert r.status_code == 200, r.text
        # 删除（非空目录拒绝 → 先删文件再删目录）
        assert client.request("DELETE", "/api/v1/admin/file/delete?path=__crud_test_dir__",
                              headers=h).status_code == 400
        assert client.request("DELETE", "/api/v1/admin/file/delete?path=__crud_test_dir__/改名后.txt",
                              headers=h).status_code == 200
        assert client.request("DELETE", "/api/v1/admin/file/delete?path=__crud_test_dir__",
                              headers=h).status_code == 200
        # data 根目录项保护
        assert client.request("DELETE", "/api/v1/admin/file/delete?path=datasets",
                              headers=h).status_code == 400
    finally:
        sess = db.Session()
        try:
            u = sess.query(User).filter_by(id=uid).first()
            if u:
                sess.delete(u)
            sess.commit()
        finally:
            sess.close()


# ===================== AI 会话标题 =====================

def test_text_of_normalizes_list_content():
    """图片消息 content 是 list——归一化后 .strip() 安全（曾炸生产：'list' object
    has no attribute 'strip'，/chat/save 标题判断路径）"""
    from yuanai_core.core.message import text_of
    assert text_of([{"type": "text", "text": "看图"},
                    {"type": "image_url", "image_url": {"url": "data:..."}}]) == "看图"
    assert text_of([{"type": "image_url", "image_url": {}}]) == ""   # 纯图片无文本
    assert text_of("plain") == "plain"
    assert text_of(None) == ""


def test_title_is_auto_heuristic():
    from api.v1.chat.title_gen import _is_auto_title
    assert _is_auto_title("新对话", "任何") is True
    assert _is_auto_title("", "任何") is True
    long = "x" * 100
    assert _is_auto_title(long[:80] + "...", long) is True
    assert _is_auto_title("帮我分析销售数据", "帮我分析销售数据") is True   # 首条消息截断式 = 自动标题
    assert _is_auto_title("销售复盘报告", "帮我分析销售数据") is False     # 用户手改/已生成
    # C 修复：前端 50 字截断口径（含 ...）同样识别为自动标题
    long50 = "y" * 60
    assert _is_auto_title(long50[:50] + "...", long50) is True
    assert _is_auto_title("z" * 50 + "...", "z" * 51) is True               # 51 字首条 → 50 字截断
    assert _is_auto_title("x" * 80, "x" * 81) is False                      # 无省略号的 80 字非截断式


def test_generate_title_updates_db(db, monkeypatch):
    """mock LLM → 标题更新 + 缓存清理；已非自动标题则跳过"""
    import uuid
    from api.v1.chat.title_gen import generate_title
    from db.session import ChatSession

    sid = str(uuid.uuid4())
    db.create_session(title="新对话")
    # create_session 生成的 session_id 是随机的，需要拿到；改为固定创建
    from db.session import ChatSession
    sess0 = db.Session()
    try:
        row = sess0.query(ChatSession).order_by(ChatSession.id.desc()).first()
        real_sid = row.session_id
    finally:
        sess0.close()
    sid = real_sid
    db.add_chat(sid, "user", "帮我分析一下上个月的销售数据趋势")
    db.add_chat(sid, "assistant", "好的，上个月销售整体上涨 15%...")

    class FakeResp:
        content = "销售数据趋势分析"

    class FakeLLM:
        def invoke(self, msgs):
            return FakeResp()

    monkeypatch.setattr("yuanai_core.core.lc.get_llm", lambda *a, **kw: FakeLLM())
    try:
        assert generate_title(sid, db.get_chats(sid)) is True
        sess = db.Session()
        try:
            row = sess.query(ChatSession).filter_by(session_id=sid).first()
            assert row.title == "销售数据趋势分析"
        finally:
            sess.close()
        # 再跑：标题已非自动 → 跳过
        assert generate_title(sid, db.get_chats(sid)) is False
    finally:
        db.delete_session(sid)


def test_retention_analytics_no_crash(db):
    """留存分析：有注册+访问数据时正常返回矩阵（regression：date.date() 崩溃）"""
    from db.session import VisitLog

    uid = db.register_user("__ret_test__", "test123")["id"]
    try:
        db.record_visit("/chat", "127.0.0.1", "ua", uid)
        r = db.query_retention_analytics(days=30)
        assert set(r) >= {"daily", "matrix"}
        assert isinstance(r["matrix"], list)
    finally:
        sess = db.Session()
        try:
            sess.query(VisitLog).filter_by(user_id=uid).delete()
            from db.session import User
            u = sess.query(User).filter_by(id=uid).first()
            if u:
                sess.delete(u)
            sess.commit()
        finally:
            sess.close()


# ===================== CC 桥接记忆端点 =====================

def test_bridge_memory_endpoint(client, db):
    """agent 凭据 401 矩阵 + 合并写用户记忆"""
    from db.session import AgentDevice, User
    import uuid as _uuid

    uid = db.register_user("__bm_user__", "test123")["id"]
    secret = "bm-secret-" + _uuid.uuid4().hex[:8]
    sess = db.Session()
    try:
        dev = AgentDevice(install_code="BM-" + _uuid.uuid4().hex[:8],
                          agent_secret=secret, machine_name="bm", user_id=uid)
        sess.add(dev)
        sess.commit()
        dev_id = dev.id
    finally:
        sess.close()
    h = {"X-Agent-Id": str(dev_id), "X-Agent-Secret": secret}
    try:
        # 401：坏 secret
        r = client.post("/api/v1/agent/bridge-memory",
                        json={"user_id": uid, "facts": ["x"]},
                        headers={"X-Agent-Id": str(dev_id), "X-Agent-Secret": "wrong"})
        assert r.status_code == 401
        # 正常写入
        r = client.post("/api/v1/agent/bridge-memory",
                        json={"user_id": uid, "facts": ["用户喜欢跑步", "用户怕辣"]},
                        headers=h)
        assert r.status_code == 200
        assert r.json()["added"] == 2
        mem = db.get_user_memory(uid)
        assert "用户喜欢跑步" in mem and "用户怕辣" in mem
        # 重复写入去重
        r = client.post("/api/v1/agent/bridge-memory",
                        json={"user_id": uid, "facts": ["用户怕辣"]}, headers=h)
        assert r.json()["added"] == 0
    finally:
        db.update_user_memory(uid, "")
        sess = db.Session()
        try:
            sess.query(AgentDevice).filter_by(id=dev_id).delete()
            u = sess.query(User).filter_by(id=uid).first()
            if u:
                sess.delete(u)
            sess.commit()
        finally:
            sess.close()
