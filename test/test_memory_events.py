"""V1-3 记忆条目事件化测试（2026-11-06）

覆盖：v2 存量懒迁移补 id / 替代链（supersedes/superseded_by）/ 只归档不删除
（delete_fact、rewrite、apply_entries 的清单外行）/ 命中统计 mark_hit /
淘汰三步 run_maintenance（superseded 7 天、零命中 90 天、相似冲突队列）/
read_memory 不返回归档项（验收三点的第三点）。
"""
import json
import os
import time

import pytest

from yuanai_core import memory_store


@pytest.fixture()
def uid(tmp_path, monkeypatch):
    import utils.data_path
    monkeypatch.setattr(utils.data_path, "root_path", lambda: str(tmp_path))
    # 重置进程内节流（维护/命中写回）
    memory_store._maintained_at.clear()
    memory_store._last_hit_write.clear()
    return 42


def _write_v2(tmp_path, rows):
    d = tmp_path / "data" / ".yuan" / "42"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "facts.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ---------------- 存量迁移与 id ----------------

def test_v2_lazy_migration_adds_id(uid, tmp_path):
    """v2 存量行首次读取 → 每条补发 id/status（懒迁移）"""
    _write_v2(tmp_path, [
        {"text": "用户是数据分析师", "created_at": "2026-10-01T10:00:00.000000",
         "type": "chat", "source": "fold"},
    ])
    entries = memory_store.load_entries(uid)
    assert len(entries) == 1
    e = entries[0]
    assert e["id"].startswith("f_") and len(e["id"]) == 14
    assert e["status"] == "active"
    assert e["hit_count"] == 0
    # 落盘后再次读取 id 稳定
    again = memory_store.load_entries(uid)
    assert again[0]["id"] == e["id"]


# ---------------- 替代链 ----------------

def test_add_facts_upgrade_supersedes_chain(uid, tmp_path):
    _write_v2(tmp_path, [
        {"text": "用户是数据分析师", "created_at": "2026-10-01T10:00:00.000000",
         "type": "chat", "source": "fold"},
    ])
    memory_store.add_facts(uid, ["用户是数据分析师，常用 pandas"],
                           source="fold", session_id="s1", turn=3)
    active = memory_store.load_entries(uid)
    assert [e["text"] for e in active] == ["用户是数据分析师，常用 pandas"]
    # 新行 supersedes 旧行；旧行 superseded 不对外可见但可查
    assert active[0]["supersedes"]
    all_entries = memory_store.load_entries(uid, include_archived=True)
    old_row = [e for e in all_entries if e["status"] == "superseded"]
    assert len(old_row) == 1
    assert old_row[0]["superseded_by"] == active[0]["id"]
    assert old_row[0]["superseded_at"]
    # 来源细化：session_id/turn 落在新行
    assert active[0]["session_id"] == "s1" and active[0]["turn"] == 3


def test_add_facts_equal_key_keeps_single_row(uid, tmp_path):
    memory_store.add_facts(uid, ["喜欢喝咖啡", "喜欢喝咖啡"])
    assert [e["text"] for e in memory_store.load_entries(uid)] == ["喜欢喝咖啡"]


# ---------------- 只归档不删除 ----------------

def test_delete_fact_archives_not_deletes(uid, tmp_path):
    memory_store.add_facts(uid, ["事实A", "事实B"])
    res = memory_store.delete_fact(uid, "事实A")
    assert res["deleted"] == 1
    assert [e["text"] for e in memory_store.load_entries(uid)] == ["事实B"]
    # 归档行保留在文件里（include_archived 可查）
    all_entries = memory_store.load_entries(uid, include_archived=True)
    texts = {e["text"]: e["status"] for e in all_entries}
    assert texts["事实A"] == "archived" and texts["事实B"] == "active"


def test_rewrite_archives_removed_lines(uid, tmp_path):
    memory_store.add_facts(uid, ["旧记忆1", "旧记忆2"])
    res = memory_store.rewrite(uid, ["旧记忆2", "新记忆"])
    assert [e["text"] for e in memory_store.load_entries(uid)] == ["旧记忆2", "新记忆"]
    all_entries = memory_store.load_entries(uid, include_archived=True)
    statuses = {e["text"]: e["status"] for e in all_entries}
    assert statuses["旧记忆1"] == "archived"  # 只归档不删除


def test_apply_entries_archives_removed(uid, tmp_path):
    memory_store.add_facts(uid, ["条目1", "条目2"])
    kept = [e for e in memory_store.load_entries(uid) if e["text"] == "条目1"]
    memory_store.apply_entries(uid, kept)
    assert [e["text"] for e in memory_store.load_entries(uid)] == ["条目1"]
    all_entries = memory_store.load_entries(uid, include_archived=True)
    assert any(e["text"] == "条目2" and e["status"] == "archived" for e in all_entries)


# ---------------- 命中统计 ----------------

def test_mark_hit_updates_stats(uid, tmp_path, monkeypatch):
    import utils.data_path
    memory_store.add_facts(uid, ["事实X"])
    memory_store.load_facts(uid, mark_hit=True)
    entries = memory_store.load_entries(uid)
    assert entries[0]["hit_count"] == 1 and entries[0]["last_hit"]
    # 60s 节流：清除节流后连续两次注入只写回一次（hit 从 1 → 2 而非 3）
    memory_store._last_hit_write.clear()
    memory_store.load_facts(uid, mark_hit=True)
    memory_store.load_facts(uid, mark_hit=True)
    assert memory_store.load_entries(uid)[0]["hit_count"] == 2


# ---------------- 淘汰三步 ----------------

def test_maintenance_superseded_7d_archives(uid, tmp_path):
    memory_store.add_facts(uid, ["旧版本事实"])
    memory_store.add_facts(uid, ["旧版本事实的更详细版本"])
    all_entries = memory_store.load_entries(uid, include_archived=True)
    sup = [e for e in all_entries if e["status"] == "superseded"][0]
    # 把 superseded_at 拨回 8 天前
    from datetime import datetime, timedelta
    sup["superseded_at"] = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%S.%f")
    memory_store._write_jsonl(uid, all_entries)
    memory_store._maintained_at.clear()
    res = memory_store.run_maintenance(uid)
    assert res["archived"] >= 1
    all2 = memory_store.load_entries(uid, include_archived=True)
    assert all(e["status"] != "superseded" for e in all2)  # 全部转 archived


def test_maintenance_zero_hit_90d_archives(uid, tmp_path):
    memory_store.add_facts(uid, ["从未被使用的记忆"])
    entries = memory_store.load_entries(uid)
    from datetime import datetime, timedelta
    entries[0]["created_at"] = (datetime.now() - timedelta(days=91)).strftime("%Y-%m-%dT%H:%M:%S.%f")
    memory_store._write_jsonl(uid, entries)
    memory_store._maintained_at.clear()
    res = memory_store.run_maintenance(uid)
    assert res["archived"] >= 1
    assert memory_store.load_entries(uid) == []


def test_maintenance_similarity_conflicts_queue(uid, tmp_path):
    # 相似但互不包含的两行（包含关系会被去重升级成替代链，走不到冲突队列）
    memory_store.add_facts(uid, [
        "用户住在北京市朝阳区望京街道",
        "用户住在北京市朝阳区望京街区",
    ])
    memory_store._maintained_at.clear()
    res = memory_store.run_maintenance(uid)
    assert res["conflicts"] >= 1
    conflicts = memory_store.list_conflicts(uid)
    assert conflicts and conflicts[0]["similarity"] >= 0.9
    assert "a_id" in conflicts[0] and "b_id" in conflicts[0]


# ---------------- 验收：read_memory 不返回归档项 ----------------

def test_load_facts_excludes_archived_and_superseded(uid, tmp_path):
    memory_store.add_facts(uid, ["可见事实"])
    memory_store.add_facts(uid, ["将被打叉的事实"])
    memory_store.delete_fact(uid, "将被打叉的事实")
    facts = memory_store.load_facts(uid)
    assert facts == ["可见事实"]


if __name__ == "__main__":
    print("测试入口：pytest test/test_memory_events.py -v")
