"""CC 工作目录可配置化回归（2026-11）

背景：此前工作目录只能靠系统环境变量 CC_PROJECT_DIR 指定（改完要重启
Windows 终端才生效），且 PROJECT_ROOT 在模块导入时固化（运行期改不动）。
本次改动：新增数据根 cc_config.json 持久化配置 + resolve_project_dir()
单一解析器；bridge_policy 的 Write/Edit 边界与 spawn cwd 改为动态解析。

覆盖：① 配置文件位置 ② 设置/清除/读回 ③ env > config > 默认 优先级
④ 配置失效（目录被删）自动回落 ⑤ 非法目标拒绝 ⑥ 坏 JSON 容错
⑦ Write/Edit 边界随配置切换
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def data_root(tmp_path, monkeypatch):
    """隔离数据根，并清掉 env 覆盖（保证测的是配置链路）"""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("CC_PROJECT_DIR", raising=False)
    return tmp_path / "XiaoYuanAI"


def test_config_file_under_data_root(data_root):
    from agent import cc_workspace
    assert cc_workspace.config_file() == str(data_root / "cc_config.json")


def test_set_and_resolve(data_root, tmp_path):
    from agent import cc_workspace
    target = tmp_path / "repo"
    target.mkdir()
    p = cc_workspace.set_project_dir(str(target))
    assert p == os.path.abspath(str(target))
    saved = json.loads((data_root / "cc_config.json").read_text("utf-8"))
    assert saved["project_dir"] == p
    assert cc_workspace.resolve_project_dir() == p
    assert cc_workspace.resolve_source() == "config"
    # 清除后回落默认根（源码模式 → root_path()）
    assert cc_workspace.clear_project_dir() is True
    from utils.data_path import root_path
    assert cc_workspace.resolve_project_dir() == root_path()


def test_clear_when_empty_returns_false(data_root):
    from agent import cc_workspace
    assert cc_workspace.clear_project_dir() is False


def test_env_overrides_config(data_root, tmp_path, monkeypatch):
    from agent import cc_workspace
    cfg_dir = tmp_path / "from_config"
    cfg_dir.mkdir()
    env_dir = tmp_path / "from_env"
    env_dir.mkdir()
    cc_workspace.set_project_dir(str(cfg_dir))
    monkeypatch.setenv("CC_PROJECT_DIR", str(env_dir))
    assert cc_workspace.resolve_project_dir() == os.path.abspath(str(env_dir))
    assert cc_workspace.resolve_source() == "env"


def test_stale_config_falls_back(data_root, tmp_path):
    """配置指向已删除目录 → 自动回落默认根（配置失效不能拖垮委派）"""
    from agent import cc_workspace
    gone = tmp_path / "gone"
    gone.mkdir()
    cc_workspace.set_project_dir(str(gone))
    gone.rmdir()
    assert cc_workspace.get_configured_dir() == ""
    from utils.data_path import root_path
    assert cc_workspace.resolve_project_dir() == root_path()


@pytest.mark.parametrize("bad", ["", "   ", os.path.join("Z:\\", "__nope__", "x")])
def test_validate_rejects_missing_or_empty(data_root, bad):
    from agent import cc_workspace
    with pytest.raises(ValueError):
        cc_workspace.validate_target(bad)


def test_validate_rejects_drive_root_and_home(data_root):
    from agent import cc_workspace
    with pytest.raises(ValueError):
        cc_workspace.validate_target("C:\\")
    with pytest.raises(ValueError):
        cc_workspace.validate_target(os.path.expanduser("~"))


def test_corrupt_config_is_ignored(data_root):
    from agent import cc_workspace
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "cc_config.json").write_text("{not json", encoding="utf-8")
    assert cc_workspace.read_config() == {}
    assert cc_workspace.get_configured_dir() == ""


def test_bridge_policy_follows_config(data_root, tmp_path):
    """Write/Edit 边界随配置切换（动态解析，不受导入时机限制）"""
    from agent import bridge_policy, cc_workspace
    target = tmp_path / "repo"
    target.mkdir()
    cc_workspace.set_project_dir(str(target))
    root = bridge_policy.current_project_root()
    assert os.path.normcase(str(root)) == os.path.normcase(os.path.abspath(str(target)))
    inside = str(target / "a.py")
    outside = str(tmp_path / "other.py")
    assert bridge_policy.classify("Write", {"file_path": inside}) == "allow"
    assert bridge_policy.classify("Write", {"file_path": outside}) == "deny"


def test_ensure_cc_workspace_is_alias(data_root, tmp_path):
    """旧调用点兼容：ensure_cc_workspace() 等价 resolve_project_dir()"""
    from agent import cc_workspace
    target = tmp_path / "repo"
    target.mkdir()
    cc_workspace.set_project_dir(str(target))
    assert cc_workspace.ensure_cc_workspace() == cc_workspace.resolve_project_dir()
