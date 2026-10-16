# -*- coding: utf-8 -*-
"""Agent 安装包化测试 — frozen 数据根 / 安装位置判定 / 旧数据迁移

运行：pytest test/test_agent_bootstrap.py -v（零网络）
"""
import os
import sys
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from utils import data_path  # noqa: E402


def test_root_path_frozen_uses_localappdata(monkeypatch, tmp_path):
    """exe 模式：数据根固定 %LOCALAPPDATA%\\XiaoYuanAI，与 cwd/exe 位置无关"""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("APP_HOME", "")  # 清掉容器分支
    root = data_path.root_path()
    assert root == os.path.join(str(tmp_path), "XiaoYuanAI")
    assert os.path.isdir(root)  # 自动创建
    # 与 cwd 无关（桌面双击场景）
    desktop = os.path.join(str(tmp_path), "Desktop")
    os.makedirs(desktop, exist_ok=True)
    monkeypatch.chdir(desktop)
    assert data_path.root_path() == os.path.join(str(tmp_path), "XiaoYuanAI")


def test_root_path_dev_mode_unchanged(monkeypatch, tmp_path):
    """开发模式（非 frozen）：保持 cwd 逻辑不变"""
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.delenv("APP_HOME", raising=False)
    monkeypatch.chdir(str(tmp_path))
    assert data_path.root_path() == str(tmp_path)


def test_is_frozen_in_install_dir(monkeypatch, tmp_path):
    """exe 位于 bin 子目录 = 已安装；其他位置 = 需引导安装"""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    bin_dir = os.path.join(str(tmp_path), "XiaoYuanAI", "bin")
    os.makedirs(bin_dir, exist_ok=True)
    monkeypatch.setattr(sys, "executable", os.path.join(bin_dir, "x.exe"))
    assert data_path.is_frozen_in_install_dir() is True

    monkeypatch.setattr(sys, "executable", os.path.join(str(tmp_path), "Desktop", "x.exe"))
    assert data_path.is_frozen_in_install_dir() is False

    # 非 frozen（开发模式）恒 True（不触发引导）
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert data_path.is_frozen_in_install_dir() is True


def test_migrate_old_data(tmp_path, monkeypatch):
    """exe 旁 data/ 存在且新根无 data → 整体迁移；已有则不覆盖"""
    from agent import bootstrap
    exe_dir = os.path.join(str(tmp_path), "old_place")
    install_dir = os.path.join(str(tmp_path), "new_place")
    os.makedirs(exe_dir, exist_ok=True)
    os.makedirs(install_dir, exist_ok=True)
    old_data = os.path.join(exe_dir, "data")
    os.makedirs(old_data, exist_ok=True)
    with open(os.path.join(old_data, "agent_identity.json"), "w", encoding="utf-8") as f:
        f.write('{"agent_id": 7}')

    monkeypatch.setattr(bootstrap, "_exe_dir", lambda: exe_dir)
    assert bootstrap._migrate_old_data(install_dir) is True
    assert os.path.isfile(os.path.join(install_dir, "data", "agent_identity.json"))

    # 已迁移过 → 再次调用不覆盖（返回 False）
    with open(os.path.join(install_dir, "data", "agent_identity.json"), "w", encoding="utf-8") as f:
        f.write('{"agent_id": 9}')
    assert bootstrap._migrate_old_data(install_dir) is False
    with open(os.path.join(install_dir, "data", "agent_identity.json"), encoding="utf-8") as f:
        assert "9" in f.read()  # 不被旧数据覆盖

    # 无旧数据 → False
    monkeypatch.setattr(bootstrap, "_exe_dir", lambda: os.path.join(str(tmp_path), "empty"))
    os.makedirs(os.path.join(str(tmp_path), "empty"), exist_ok=True)
    assert bootstrap._migrate_old_data(install_dir) is False


if __name__ == "__main__":
    print("测试入口：pytest test/test_agent_bootstrap.py -v")
