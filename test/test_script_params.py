# -*- coding: utf-8 -*-
"""S1.6 脚本派发参数注入修复测试 — 类型化校验 + 拒绝时不启动子进程

纯离线（真实脚本注册，monkeypatch subprocess.Popen 断言未被调用）。
运行：pytest test/test_script_params.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')


@pytest.fixture(scope="module")
def registry():
    from agent.scripts.registry import ScriptRegistry
    return ScriptRegistry("agent/datanalysis/scripts")


@pytest.fixture(scope="module")
def crawl_registry():
    from agent.scripts.registry import ScriptRegistry
    return ScriptRegistry("agent/datanalysis/crawl")


def test_all_scripts_registered_with_schemas(registry, crawl_registry):
    """9+1 个脚本全部注册且带类型化参数声明"""
    names = set(registry._scripts) | set(crawl_registry._scripts)
    assert len(names) >= 10
    for name, handle in {**registry._scripts, **crawl_registry._scripts}.items():
        if handle._param_order:
            # 有参数声明的脚本，每个参数必须有 schema（显式或启发式）
            for p in handle._param_order:
                assert p in handle._param_schemas, f"{name}: {p} 缺 schema"


def test_path_traversal_rejected_no_subprocess(registry, monkeypatch):
    """file_path=../../.env → 返回路径越界且不启动子进程（Popen 未被调用）"""
    import subprocess

    called = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: called.append(a) or (_ for _ in ()).throw(AssertionError("不应启动子进程")))

    out = registry.run("基因表达分布分析", {"file_path": "../../.env"})
    assert "路径越界" in out, out

    out = registry.run("RFM客户分群", {"file_path": "C:\\Users\\x\\.ssh\\id_rsa"})
    assert "路径越界" in out, out


def test_legal_relative_path_allowed(registry):
    """合法相对路径（data/ 内）放行"""
    out = registry.run("基因表达分布分析", {"file_path": "data/user/from/订单明细.xlsx"})
    # 脚本本身会报文件不存在（exit!=0），只要不是参数校验失败即通过
    assert "参数校验失败" not in out, out


def test_int_param_rejected(registry, monkeypatch):
    import subprocess
    called = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: called.append(a) or (_ for _ in ()).throw(AssertionError("不应启动子进程")))

    out = registry.run("描述性统计分析", {"dataset_id": "1; rm -rf /"})
    assert "参数校验失败" in out, out
    out = registry.run("描述性统计分析", {"dataset_id": "../../.env"})
    assert "参数校验失败" in out, out


def test_enum_choices_rejected(registry, monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("不应启动子进程")))

    out = registry.run("描述性统计分析", {"chart_type": "all; rm -rf /"})
    assert "参数校验失败" in out, out
    out = registry.run("相关性分析", {"method": "pearson; cat /etc/passwd"})
    assert "参数校验失败" in out, out


def test_dash_prefix_rejected(registry, monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("不应启动子进程")))

    out = registry.run("数据预处理", {"operations": "--help"})
    assert "参数校验失败" in out, out


def test_valid_params_pass(registry):
    """合法参数组合通过校验（脚本执行失败 ≠ 校验失败）"""
    out = registry.run("描述性统计分析", {"dataset_id": "1", "chart_type": "all"})
    assert "参数校验失败" not in out, out


def test_crawl_url_validated(crawl_registry, monkeypatch):
    import subprocess
    called = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: called.append(a) or (_ for _ in ()).throw(AssertionError("不应启动子进程")))

    # 内网 URL → 拒绝且不启动子进程
    out = crawl_registry.run("通用网页采集", {"url": "http://127.0.0.1:8000/"})
    assert "参数校验失败" in out and "URL" in out, out

    # 合法外网 URL + int 参数 → 通过校验（不拦）
    out = crawl_registry.run("通用网页采集", {"url": "https://example.com/", "max_pages": "3"})
    assert "参数校验失败" not in out, out


def test_guess_type_heuristics():
    """旧格式启发式：path|file|dir → path；id|num|count 等 → int；其余 enum"""
    from agent.scripts.registry import _guess_type
    assert _guess_type("file_path") == "path"
    assert _guess_type("output_dir") == "path"
    assert _guess_type("dataset_id") == "int"
    assert _guess_type("top_n") == "int"
    assert _guess_type("max_pages") == "int"
    assert _guess_type("chart_type") == "enum"
    assert _guess_type("target_col") == "enum"


def test_validate_param_matrix():
    from agent.scripts.registry import _validate_param

    # int
    assert not _validate_param("x", "123", {"type": "int"})
    assert _validate_param("x", "12.5", {"type": "int"})
    assert _validate_param("x", "99999999999", {"type": "int"})  # 超 10 位
    # float
    assert not _validate_param("x", "0.2", {"type": "float"})
    assert _validate_param("x", "0.2;ls", {"type": "float"})
    # enum
    assert not _validate_param("x", "订单金额", {})
    assert _validate_param("x", "../etc", {})
    assert _validate_param("x", "a/b", {})
    assert _validate_param("x", "", {})
    # choices
    assert not _validate_param("x", "all", {"choices": ["all", "static"]})
    assert _validate_param("x", "other", {"choices": ["all", "static"]})
    # - 前缀
    assert _validate_param("x", "-h", {})


if __name__ == "__main__":
    print("测试入口：pytest test/test_script_params.py -v")
