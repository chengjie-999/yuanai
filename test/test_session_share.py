"""V1-4 会话分享测试（2026-11-06）

覆盖：归属校验/空会话 400/分享生成静态 HTML（完整正文 + AI 标识 + 举报入口
+ robots 收录 + META 剥离）/公开 GET（未分享 404）/取消分享下线/HTML 转义。
"""
import json
import secrets

import pytest

from api.v1.chat.share import render_share_html
from db.session import get_db


def _db_or_skip():
    try:
        return get_db()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


@pytest.fixture(scope="module")
def db():
    return _db_or_skip()


@pytest.fixture()
def user_session(db):
    """用户 + 带消息的会话"""
    from api.v1.auth.utils import create_token
    uid = None
    with db.session() as sess:
        from db.session import User
        u = sess.query(User).filter_by(username="__share_user__").first()
        if u is None:
            r = db.register_user("__share_user__", "test1234")
            u = sess.query(User).filter_by(id=r["id"]).first()
        uid = u.id
    sid = db.create_session("分享测试会话", user_id=uid)["session_id"]
    db.add_chat(sid, "user", "你好，请介绍一下你自己")
    db.add_chat(sid, "assistant", "\x00META\x00{\"s\":\"orchestrator\"}\x00我是小元AI")
    yield {"uid": uid, "sid": sid, "token": create_token(uid, "user")}
    with db.session() as sess:
        from db.session import ChatSession, AIChat
        sess.query(AIChat).filter_by(session_id=sid).delete()
        sess.query(ChatSession).filter_by(session_id=sid).delete()
        sess.commit()


@pytest.fixture()
def shares_dir(monkeypatch, tmp_path):
    import api.v1.chat.share as sh
    monkeypatch.setattr(sh, "_shares_dir", lambda: str(tmp_path / "shares"))
    return str(tmp_path)


# ---------------- 纯函数渲染 ----------------

def test_render_html_escapes_and_contains_required_markers():
    html = render_share_html("s1", "标题", "2026-11-06 12:00",
                             [{"role": "user", "content": "<script>alert(1)</script>"}])
    assert "<script>alert(1)</script>" not in html      # 转义防注入
    assert "&lt;script&gt;" in html
    assert "AI 生成" in html                              # C5 标识
    assert "举报入口" in html                             # C7 入口
    assert 'content="index, follow"' in html              # robots 收录
    assert "canonical" in html


def test_render_html_strips_meta():
    html = render_share_html("s1", "t", "2026-11-06 12:00",
                             [{"role": "assistant",
                               "content": "\x00META\x00{\"s\":\"orchestrator\"}\x00正文"}])
    assert "正文" in html
    assert "META" not in html


# ---------------- 端点 ----------------

def test_share_roundtrip(client, db, user_session, shares_dir, monkeypatch):
    h = {"Authorization": f"Bearer {user_session['token']}"}
    # 未分享 → 公开 404
    assert client.get(f"/api/v1/share/{user_session['sid']}").status_code == 404
    # 分享
    r = client.post(f"/api/v1/chat/share/{user_session['sid']}", headers=h)
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert url == f"/api/v1/share/{user_session['sid']}"
    # 公开访问：完整正文 + 关键标识
    pub = client.get(url)
    assert pub.status_code == 200
    body = pub.text
    assert "你好，请介绍一下你自己" in body
    assert "我是小元AI" in body
    assert "AI 生成" in body and "举报入口" in body
    # 取消分享 → 下线
    d = client.delete(f"/api/v1/chat/share/{user_session['sid']}", headers=h)
    assert d.status_code == 200
    assert client.get(url).status_code == 404


def test_share_ownership_check(client, db, user_session, shares_dir):
    from api.v1.auth.utils import create_token
    with db.session() as sess:
        from db.session import User
        other = sess.query(User).filter_by(username="__share_other__").first()
        if other is None:
            rr = db.register_user("__share_other__", "test1234")
            other = sess.query(User).filter_by(id=rr["id"]).first()
    h = {"Authorization": f"Bearer {create_token(other.id, 'user')}"}
    r = client.post(f"/api/v1/chat/share/{user_session['sid']}", headers=h)
    assert r.status_code in (403, 404)
    # 未登录分享 → 401
    assert client.post(f"/api/v1/chat/share/{user_session['sid']}").status_code == 401


def test_share_empty_session_400(client, db, shares_dir):
    from api.v1.auth.utils import create_token
    with db.session() as sess:
        from db.session import User
        u = sess.query(User).filter_by(username="__share_user__").first()
        uid = u.id
    sid = db.create_session("空会话", user_id=uid)["session_id"]
    try:
        h = {"Authorization": f"Bearer {create_token(uid, 'user')}"}
        r = client.post(f"/api/v1/chat/share/{sid}", headers=h)
        assert r.status_code == 400
    finally:
        with db.session() as sess:
            from db.session import ChatSession
            sess.query(ChatSession).filter_by(session_id=sid).delete()
            sess.commit()


def test_share_bad_sid_rejected(client, user_session):
    h = {"Authorization": f"Bearer {user_session['token']}"}
    assert client.post("/api/v1/chat/share/..%2Fetc", headers=h).status_code in (400, 404)
    assert client.get("/api/v1/share/..%2Fetc").status_code == 404


if __name__ == "__main__":
    print("测试入口：pytest test/test_session_share.py -v")
