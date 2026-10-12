# -*- coding: utf-8 -*-
"""记忆自整理测试 — plan_organize 纯逻辑（零 DB）+ organize_user_memory 护栏（需 MySQL）

删除护栏（安全事故教训后的硬限制）：
  - 只删本会话内新增的行（created_at ≥ 会话首条消息时间）
  - 每用户每日删 ≤ MEMORY_ORGANIZE_DELETE_DAILY_MAX 条（Redis 计数）
  - 每次删除写审计日志 data/logs/memory_audit.log
  - 任何护栏不过 → 整单拒绝（fail-closed）
运行：pytest test/test_memory_organize.py -v
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from yuanai_core.memory import plan_organize  # noqa: E402


# ---------------- plan_organize 纯逻辑 ----------------

def _entry(text, created_at="2026-10-01T00:00:00.000000"):
    return {"text": text, "created_at": created_at, "type": "chat", "source": "fold", "file": "f.md"}


def test_plan_upgrade_reuses_created_at():
    """新行 ⊃ 旧行 → 原地升级为新行文本，created_at 复用（改写不洗白创建时间）"""
    plan = plan_organize([_entry("用户是数据分析师")],
                         ["用户是数据分析师，常用 pandas"])
    assert len(plan["kept"]) == 1 and plan["kept"][0]["text"] == "用户是数据分析师，常用 pandas"
    assert plan["kept"][0]["created_at"] == "2026-10-01T00:00:00.000000"
    assert plan["deletions"] == []


def test_plan_old_swallows_new():
    """旧行 ⊃ 新行 → 保留旧行（更完整的不被缩水）"""
    plan = plan_organize([_entry("在做跨境电商项目")], ["跨境电商"])
    assert [e["text"] for e in plan["kept"]] == ["在做跨境电商项目"]
    assert plan["deletions"] == []


def test_plan_missing_old_becomes_deletion():
    plan = plan_organize([_entry("用户怕辣"), _entry("用户在杭州")], ["用户怕辣"])
    assert [e["text"] for e in plan["kept"]] == ["用户怕辣"]
    assert [d["text"] for d in plan["deletions"]] == ["用户在杭州"]


def test_plan_new_line_added():
    plan = plan_organize([_entry("用户怕辣")], ["用户怕辣", "用户在做数据分析"])
    added = [e for e in plan["kept"] if e["text"] == "用户在做数据分析"]
    assert len(added) == 1 and added[0]["created_at"] == "" and added[0]["source"] == "organize"
    assert plan["deletions"] == []


def test_plan_empty_and_placeholder_filtered():
    """空清单 → 全部旧行成为删除候选（护栏在 db 层拦截）；占位行不产生新增"""
    plan = plan_organize([_entry("用户怕辣")], ["无", "", "  "])
    assert plan["kept"] == []
    assert [d["text"] for d in plan["deletions"]] == ["用户怕辣"]


# ---------------- db 层护栏（需 MySQL，不可用则跳过） ----------------

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
def org_user(db):
    from db.session import User
    sess = db.Session()
    try:
        old = sess.query(User).filter_by(username="__mem_org_test__").first()
        if old:
            sess.delete(old)
            sess.commit()
    finally:
        sess.close()
    r = db.register_user("__mem_org_test__", "test123")
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


@pytest.fixture
def org_env(tmp_path, monkeypatch):
    """记忆目录 + 审计日志都隔离到 tmp（.yuan 经 memory_store.root_path，audit 经 utils.data_path）"""
    import yuanai_core.memory_store as store
    import utils.data_path as dp
    monkeypatch.setattr(store, "root_path", lambda: str(tmp_path))
    monkeypatch.setattr(dp, "root_path", lambda: str(tmp_path))
    return tmp_path


def _make_session(db, uid, sid="mem_org_sid"):
    """直接插一条会话首条消息（create_time 由 DB 生成 = 会话开始边界）"""
    from db.session import AIChat
    sess = db.Session()
    try:
        sess.add(AIChat(session_id=sid, user_id=uid, role="user", content="你好"))
        sess.commit()
    finally:
        sess.close()
    return sid


def _seed_memory(db, uid, old_text="用户怕辣", new_text="用户在做数据分析"):
    """先建会话（时间边界），再写两条记忆：旧（2020，会话前）+ 新（now，会话内）"""
    import yuanai_core.memory_store as store
    sid = _make_session(db, uid)
    store.apply_entries(uid, [_entry(old_text, "2020-01-01T00:00:00.000000")])
    store.add_facts(uid, [new_text], source="fold")
    return sid


def test_organize_delete_session_new_ok(db, org_user, org_env):
    """删本会话内新增的行 → 放行，审计日志落盘"""
    uid = org_user["id"]
    sid = _seed_memory(db, uid)
    r = db.organize_user_memory(uid, ["用户怕辣"], sid)  # 清单缺「用户在做数据分析」→ 删它
    assert r["ok"], r
    assert r["deleted"] == 1 and r["total"] == 1
    assert db.get_user_memory(uid) == "用户怕辣"
    audit = os.path.join(str(org_env), "data", "logs", "memory_audit.log")
    assert os.path.isfile(audit)
    assert "用户在做数据分析" in open(audit, encoding="utf-8").read()


def test_organize_delete_presession_refused(db, org_user, org_env):
    """删会话之前创建的行 → 整单拒绝（fail-closed）"""
    uid = org_user["id"]
    sid = _seed_memory(db, uid)
    r = db.organize_user_memory(uid, ["用户在做数据分析"], sid)  # 清单缺「用户怕辣」（2020）→ 删它
    assert not r["ok"] and "本会话之前" in r["detail"]
    assert db.get_user_memory(uid) == "用户怕辣\n用户在做数据分析"  # 未动


def test_organize_delete_without_session_refused(db, org_user, org_env):
    uid = org_user["id"]
    _seed_memory(db, uid)
    r = db.organize_user_memory(uid, ["用户怕辣"], "")  # 无会话 → 删除禁止
    assert not r["ok"] and "会话起始时间" in r["detail"]


def test_organize_quota_exceeded_refused(db, org_user, org_env, monkeypatch):
    uid = org_user["id"]
    sid = _seed_memory(db, uid)
    monkeypatch.setattr("api.v1.db_helpers.consume_daily_quota", lambda *a, **k: False)
    r = db.organize_user_memory(uid, ["用户怕辣"], sid)
    assert not r["ok"] and "额度" in r["detail"]


def test_organize_pure_rewrite_no_deletion(db, org_user, org_env):
    """清单覆盖全部旧行（含升级）→ 无删除动作，即使无会话也放行"""
    uid = org_user["id"]
    sid = _seed_memory(db, uid)
    r = db.organize_user_memory(uid, ["用户怕辣", "用户在做数据分析，常用 pandas"], "")
    assert r["ok"] and r["deleted"] == 0
    assert "常用 pandas" in db.get_user_memory(uid)


if __name__ == "__main__":
    print("测试入口：pytest test/test_memory_organize.py -v")
