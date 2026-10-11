# -*- coding: utf-8 -*-
"""记忆文件存储测试 — data/.yuan/（tmp 目录隔离，零 DB 零 LLM）

运行：pytest test/test_memory_store.py -v
"""
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from yuanai_core import memory_store as store  # noqa: E402


@pytest.fixture
def memdir(tmp_path, monkeypatch):
    """把 store 的 root_path 指到临时目录，隔离 data/.yuan/"""
    monkeypatch.setattr(store, "root_path", lambda: str(tmp_path))
    return tmp_path


def _yuan_dir(memdir, uid):
    return os.path.join(str(memdir), "data", ".yuan", str(uid))


def test_add_and_load(memdir):
    store.add_facts(1, ["用户是数据分析师", "用户怕辣"])
    assert store.load_facts(1) == ["用户是数据分析师", "用户怕辣"]
    assert os.path.isfile(os.path.join(_yuan_dir(memdir, 1), "MEMORY.md"))


def test_add_dedup_and_upgrade(memdir):
    store.add_facts(1, ["用户是数据分析师"])
    r = store.add_facts(1, ["用户是数据分析师"])
    assert r["added"] == 0  # 等键跳过
    r = store.add_facts(1, ["用户是数据分析师，常用 pandas"])
    assert r["added"] == 0  # 升级替换不新增
    assert store.load_facts(1) == ["用户是数据分析师，常用 pandas"]


def test_placeholder_never_stored(memdir):
    store.add_facts(1, ["无", "暂无", "用户怕辣"])
    assert store.load_facts(1) == ["用户怕辣"]


def test_limits_drop_oldest(memdir):
    store.add_facts(1, ["事实一"], max_items=2)
    store.add_facts(1, ["事实二", "事实三"], max_items=2)
    assert store.load_facts(1) == ["事实二", "事实三"]


def test_delete_exact_and_substring(memdir):
    store.add_facts(1, ["用户是数据分析师", "用户怕辣", "用户在杭州"])
    r = store.delete_fact(1, "用户怕辣")
    assert r["deleted"] == 1 and r["total"] == 2
    assert store.load_facts(1) == ["用户是数据分析师", "用户在杭州"]
    # 唯一子串匹配
    r = store.delete_fact(1, "杭州")
    assert r["deleted"] == 1
    # 无命中
    r = store.delete_fact(1, "不存在的内容")
    assert r["deleted"] == 0
    # 多条命中 → asked_more（互不包含的两条，避开升级替换语义）
    store.add_facts(1, ["用户喜欢猫", "用户喜欢狗"])
    r = store.delete_fact(1, "用户喜欢")
    assert r["deleted"] == 0 and r["asked_more"] is True


def test_rewrite_and_clear(memdir):
    store.add_facts(1, ["事实一", "事实二"])
    r = store.rewrite(1, ["新事实一", "新事实二", "新事实三"])
    assert r["total"] == 3
    assert store.load_facts(1) == ["新事实一", "新事实二", "新事实三"]
    store.clear(1)
    assert store.load_facts(1) == []


def test_roundtrip_frontmatter(memdir):
    """frontmatter 中文与特殊字符往返无损"""
    fact = "用户常用 Python:pandas 与 MySQL"
    store.add_facts(1, [fact])
    assert store.load_facts(1) == [fact]
