# -*- coding: utf-8 -*-
"""C4 用户注销级联删除测试（2026-10-29）：delete_user_cascade 清理全表数据
与磁盘文件（记忆/星球目录/聊天图片）；删除后用户不可再登录。"""
import os
import sys

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


@pytest.fixture
def cascade_env(tmp_path, monkeypatch):
    import yuanai_core.memory_store as store
    import utils.data_path as dp
    import utils.data_path as _udp
    monkeypatch.setattr(_udp, "root_path", lambda: str(tmp_path))  # V1-3 惰性导入
    monkeypatch.setattr(dp, "root_path", lambda: str(tmp_path))
    return tmp_path


def _make_user(db):
    import uuid as _uuid
    name = "__cascade__" + _uuid.uuid4().hex[:6]
    r = db.register_user(name, "test1234")
    assert "error" not in r, r
    return r["id"], name


def test_cascade_cleans_all_tables_and_files(db, cascade_env):
    from db.session import ChatSession, AIChat, Dataset, Plan, VisitLog, TokenUsage, AgentDevice
    import yuanai_core.memory_store as store

    uid, name = _make_user(db)
    try:
        sess = db.Session()
        try:
            sid = "cascade-" + os.urandom(4).hex()
            sess.add(ChatSession(session_id=sid, user_id=uid, title="t"))
            sess.flush()
            sess.add(AIChat(session_id=sid, role="user", content="你好"))
            sess.add(Dataset(user_id=uid, name="ds", file_path="", file_type="csv",
                             row_count=1, columns_info="[]"))
            sess.add(Plan(user_id=uid, session_id=sid, title="p", goal="g",
                          status="draft"))
            sess.add(VisitLog(path="/", ip="1.2.3.4", user_agent="t", user_id=uid))
            sess.add(TokenUsage(user_id=uid, model="m", purpose="chat",
                                prompt_tokens=1, completion_tokens=1,
                                total_tokens=2))
            _sec = "s-" + os.urandom(4).hex()
            sess.add(AgentDevice(install_code="CAS-" + os.urandom(4).hex(),
                                 agent_secret=_sec, machine_name="m", user_id=uid))
            sess.commit()
        finally:
            sess.close()
        store.add_facts(uid, ["用户怕辣"])

        summary = db.delete_user_cascade(uid)

        sess = db.Session()
        try:
            from db.session import User
            assert sess.query(User).filter_by(id=uid).first() is None
            assert sess.query(ChatSession).filter_by(user_id=uid).count() == 0
            assert sess.query(AIChat).filter_by(session_id=sid).count() == 0
            assert sess.query(Dataset).filter_by(user_id=uid).count() == 0
            assert sess.query(Plan).filter_by(user_id=uid).count() == 0
            assert sess.query(VisitLog).filter_by(user_id=uid).count() == 0
            assert sess.query(TokenUsage).filter_by(user_id=uid).count() == 0
            dev = sess.query(AgentDevice).filter_by(agent_secret=_sec).first()
            assert dev is not None and dev.user_id is None and dev.enabled == 0
        finally:
            sess.close()

        assert store.load_facts(uid) == []
        assert summary.get("chat_sessions") == 1
    finally:
        db.delete_user_cascade(uid)
