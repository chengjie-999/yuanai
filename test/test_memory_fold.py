# -*- coding: utf-8 -*-
"""记忆折叠集成测试 — 真 MySQL（不可用则 skip）+ mock LLM

运行：pytest test/test_memory_fold.py -v
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
def fold_user(db):
    from db.session import User

    sess = db.Session()
    try:
        old = sess.query(User).filter_by(username="__fold_test__").first()
        if old:
            sess.delete(old)
            sess.commit()
    finally:
        sess.close()
    r = db.register_user("__fold_test__", "test123")
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


def _make_session_messages(db, sid, n):
    """直接落库 n 条交替消息（绕开 /chat/save 走 add_chat）"""
    for i in range(n):
        db.add_chat(sid, "user" if i % 2 == 0 else "assistant",
                    f"消息{i}：用户说喜欢数据分析和 pandas" if i % 2 == 0 else f"回复{i}：好的")


def _cleanup(db, sid):
    db.delete_session(sid)
    from db.session import SessionMemoryState
    sess = db.Session()
    try:
        sess.query(SessionMemoryState).filter_by(session_id=sid).delete()
        sess.commit()
    finally:
        sess.close()


@pytest.fixture()
def fake_llm(monkeypatch):
    """mock _call_fold_llm：返回固定事实，并记录调用次数与 transcript 片段"""
    calls = []

    def fake(sys_prompt, user_text):
        calls.append(user_text)
        return "- 用户喜欢数据分析\n- 用户常用 pandas"

    import yuanai_core.memory as mem
    monkeypatch.setattr(mem, "_call_fold_llm", fake)
    return calls


def test_fold_normal_flow(db, fold_user, fake_llm):
    """30 条消息 → 折叠：记忆出现条目 + 游标前进（30-20=10 条被折叠）"""
    from api.v1.chat.memory_fold import run_memory_fold
    import uuid

    sid = str(uuid.uuid4())
    _make_session_messages(db, sid, 30)
    try:
        r = run_memory_fold(sid, fold_user["id"], None, None)
        assert r.get("folded") == 10, r
        assert r.get("facts") == 2
        mem = db.get_user_memory(fold_user["id"])
        assert "用户喜欢数据分析" in mem
        assert db.get_session_memory_state(sid)["folded_count"] == 10

        # 再跑一次：无新材料 → nothing_new
        r2 = run_memory_fold(sid, fold_user["id"], None, None)
        assert r2.get("skipped") == "nothing_new", r2
    finally:
        _cleanup(db, sid)
        db.update_user_memory(fold_user["id"], "")


def test_fold_llm_failure_keeps_cursor(db, fold_user, monkeypatch):
    from api.v1.chat.memory_fold import run_memory_fold
    import uuid
    import yuanai_core.memory as mem

    monkeypatch.setattr(mem, "_call_fold_llm",
                        lambda s, t: (_ for _ in ()).throw(TimeoutError("timeout")))
    sid = str(uuid.uuid4())
    _make_session_messages(db, sid, 30)
    try:
        r = run_memory_fold(sid, fold_user["id"], None, None)
        assert "llm_failed" in r.get("skipped", "")
        assert db.get_session_memory_state(sid) is None  # 游标未写
        assert db.get_user_memory(fold_user["id"]) == ""
    finally:
        _cleanup(db, sid)


def test_fold_empty_output_advances(db, fold_user, monkeypatch):
    """LLM 空输出（纯寒暄）= 遗忘：游标前进、记忆不变"""
    from api.v1.chat.memory_fold import run_memory_fold
    import uuid
    import yuanai_core.memory as mem

    monkeypatch.setattr(mem, "_call_fold_llm", lambda s, t: "")
    sid = str(uuid.uuid4())
    _make_session_messages(db, sid, 30)
    try:
        r = run_memory_fold(sid, fold_user["id"], None, None)
        assert r.get("folded") == 10, r
        assert r.get("facts") == 0
        assert db.get_session_memory_state(sid)["folded_count"] == 10
        assert db.get_user_memory(fold_user["id"]) == ""
    finally:
        _cleanup(db, sid)


def test_fold_dislike_excluded(db, fold_user, fake_llm):
    """点踩的 assistant 消息：transcript 中不含其正文"""
    from api.v1.chat.memory_fold import run_memory_fold
    import uuid
    from db.session import AIChatFeedback

    sid = str(uuid.uuid4())
    _make_session_messages(db, sid, 30)
    try:
        # 点踩第 5 条（assistant，内容含「独家秘密」）
        sess = db.Session()
        try:
            sess.add(AIChatFeedback(session_id=sid, message_index=5,
                                    disliked=1, user_id=fold_user["id"]))
            sess.commit()
        finally:
            sess.close()
        # 把第 5 条改成独特内容便于断言
        sess = db.Session()
        try:
            from db.session import AIChat
            row = sess.query(AIChat).filter_by(session_id=sid).order_by(AIChat.id).offset(5).first()
            row.content = "独家秘密：用户住在火星"
            sess.commit()
        finally:
            sess.close()

        run_memory_fold(sid, fold_user["id"], None, None)
        assert len(fake_llm) == 1
        transcript = fake_llm[0]
        assert "独家秘密" not in transcript
        assert "用户点踩" in transcript
    finally:
        _cleanup(db, sid)
        db.update_user_memory(fold_user["id"], "")


def test_fold_guard_blocks_small_material(db, fold_user, fake_llm):
    """材料太少（<5 条且 <800 字）→ 不调 LLM"""
    from api.v1.chat.memory_fold import run_memory_fold
    import uuid

    sid = str(uuid.uuid4())
    _make_session_messages(db, sid, 23)  # 超阈值(>20)，但材料只有 3 条
    try:
        r = run_memory_fold(sid, fold_user["id"], None, None)
        assert r.get("skipped") == "below_fold_guard", r
        assert len(fake_llm) == 0
    finally:
        _cleanup(db, sid)


def test_fold_below_threshold_skipped(db, fold_user, fake_llm):
    from api.v1.chat.memory_fold import run_memory_fold
    import uuid

    sid = str(uuid.uuid4())
    _make_session_messages(db, sid, 10)
    try:
        r = run_memory_fold(sid, fold_user["id"], None, None)
        assert r.get("skipped") == "below_threshold", r
        assert len(fake_llm) == 0
    finally:
        _cleanup(db, sid)


def test_fold_edit_rewind_clamps(db, fold_user, fake_llm):
    """编辑重发使消息变短：游标回夹不越界、单调不回退"""
    from api.v1.chat.memory_fold import run_memory_fold
    import uuid

    sid = str(uuid.uuid4())
    _make_session_messages(db, sid, 30)
    try:
        run_memory_fold(sid, fold_user["id"], None, None)
        assert db.get_session_memory_state(sid)["folded_count"] == 10
        # 模拟编辑重发：数组砍到 22 条（少于 folded+20=30）
        for _ in range(8):
            sess = db.Session()
            try:
                from db.session import AIChat
                last = sess.query(AIChat).filter_by(session_id=sid).order_by(AIChat.id.desc()).first()
                sess.delete(last)
                sess.commit()
            finally:
                sess.close()
        r = run_memory_fold(sid, fold_user["id"], None, None)
        # 22 条 → end=2，folded clamp 到 2 → nothing_new；游标不回退（仍 ≥10）
        assert r.get("skipped") == "nothing_new", r
        assert db.get_session_memory_state(sid)["folded_count"] >= 10
    finally:
        _cleanup(db, sid)
        db.update_user_memory(fold_user["id"], "")


if __name__ == "__main__":
    print("测试入口：pytest test/test_memory_fold.py -v")
