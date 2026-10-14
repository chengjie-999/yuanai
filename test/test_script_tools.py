# -*- coding: utf-8 -*-
"""脚本工具化测试 — key 别名/iter_handles/resolve/StructuredTool 生成（零网络零 MySQL）

融合 R1：ScriptRegistry 的每个脚本生成统筹直调的 function calling 工具，
执行仍走 registry.run（校验咽喉不变）。
运行：pytest test/test_script_tools.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from agent.scripts.registry import ScriptRegistry, SCRIPT_KEYS  # noqa: E402
from agent.scripts.tools import build_script_tools, get_registry  # noqa: E402


@pytest.fixture(scope="module")
def registry():
    return ScriptRegistry("agent/datanalysis/scripts", skill="analysis")


def test_iter_handles_public_enum(registry):
    handles = registry.iter_handles()
    assert len(handles) == 9  # analysis 9 个脚本
    names = {h.name for h in handles}
    assert "描述性统计分析" in names and "RFM客户分群" in names


def test_keys_ascii_and_unique(registry):
    keys = [h.key for h in registry.iter_handles()]
    assert len(keys) == len(set(keys))
    for k in keys:
        assert k.replace("_", "a").isalnum(), k  # ASCII 字母数字下划线
    assert set(keys) >= {"descriptive_stats", "rfm_cluster", "correlation"}


def test_script_keys_table_covers_all(registry):
    """静态别名表覆盖全部脚本（未登记的走 md5 fallback 也合法，但登记更可读）"""
    for h in registry.iter_handles():
        if h.name in SCRIPT_KEYS:
            assert h.key == SCRIPT_KEYS[h.name]


def test_resolve_dual_channel(registry):
    assert registry.resolve("描述性统计分析") == "描述性统计分析"
    assert registry.resolve("descriptive_stats") == "描述性统计分析"
    assert registry.resolve("script_descriptive_stats") == "描述性统计分析"
    assert registry.resolve("不存在的脚本") is None


def test_run_accepts_key(registry):
    out = registry.run("descriptive_stats", {}, progress_cb=lambda c, t, m: None)
    # 无参数跑真实脚本会先报参数校验/脚本错误，但绝不是「未知脚本」
    assert "未知脚本" not in out


def test_build_script_tools_schema(registry, monkeypatch):
    tools = build_script_tools(registry, skill="analysis")
    assert len(tools) == 9
    by_name = {t.name: t for t in tools}
    assert "script_rfm_cluster" in by_name
    t = by_name["script_rfm_cluster"]
    assert "数据分析" in t.description and "RFM客户分群" in t.description
    # schema 全 optional（pydantic v2 用 anyOf [T, null]，v1 用 type 数组）
    props = t.args_schema.model_json_schema().get("properties", {})
    assert props, "args_schema 应有字段"
    for fname, finfo in props.items():
        t = finfo.get("type") or []
        anyof = finfo.get("anyOf") or []
        optional = ("null" in t) or any(x.get("type") == "null" for x in anyof)
        assert optional, f"{fname} 应为 optional: {finfo}"
    # 参数名按脚本声明生成：rfm_cluster 是 file_path/user_info_path；
    # descriptive_stats 是 dataset_id
    keys = list(props.keys())
    assert "file_path" in keys and "user_info_path" in keys
    ds = by_name["script_descriptive_stats"].args_schema.model_json_schema().get("properties", {})
    assert "dataset_id" in ds


def test_tool_invoke_routes_through_registry_run(registry, monkeypatch):
    """工具函数体必须走 registry.run（校验咽喉），并透传 progress_cb 与参数"""
    tools = build_script_tools(registry, skill="analysis")
    t = {x.name: x for x in tools}["script_descriptive_stats"]
    calls = []

    def fake_run(name, params=None, progress_cb=None):
        calls.append((name, dict(params or {}), progress_cb))
        return "fake-ok"

    monkeypatch.setattr(registry, "run", fake_run)
    cb = lambda c, t_, m: None
    out = t.invoke({"dataset_id": 8})
    assert out == "fake-ok"
    name, params, cb_passed = calls[0]
    assert name == "描述性统计分析" and params == {"dataset_id": 8}
    assert cb_passed is None  # 本工具未传 progress_cb（工厂参数可传）


def test_tool_progress_cb_passed(registry, monkeypatch):
    cb = lambda c, t_, m: None
    tools = build_script_tools(registry, skill="analysis", progress_cb=cb)
    t = {x.name: x for x in tools}["script_descriptive_stats"]
    calls = []

    def fake_run(name, params=None, progress_cb=None):
        calls.append(progress_cb)
        return "ok"

    monkeypatch.setattr(registry, "run", fake_run)
    t.invoke({"dataset_id": 1})
    assert calls[0] is cb


def test_enabled_false_empty(registry):
    assert build_script_tools(registry, enabled=False) == []


def test_get_registry_skill_cache(monkeypatch):
    r = get_registry("analysis")
    assert r is not None and len(r.iter_handles()) == 9
    r2 = get_registry("collection")
    assert r2 is not None and len(r2.iter_handles()) >= 1
    assert r2.skill == "collection"
    assert r2.resolve("generic_crawl") == "通用网页采集"


if __name__ == "__main__":
    print("测试入口：pytest test/test_script_tools.py -v")
