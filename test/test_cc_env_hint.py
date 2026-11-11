# -*- coding: utf-8 -*-
"""P3 环境自述测试 — bridge_system_prompt 注入工作目录/shell/边界（零网络）

运行：pytest test/test_cc_env_hint.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # noqa: E402
sys.stdout.reconfigure(encoding='utf-8')

from agent import claude_loop  # noqa: E402
from agent import cc_workspace  # noqa: E402


def test_bridge_prompt_contains_env_hint(monkeypatch, tmp_path):
    monkeypatch.setattr(cc_workspace, "resolve_project_dir", lambda: str(tmp_path))
    prompt = claude_loop.bridge_system_prompt()
    assert str(tmp_path) in prompt                    # 工作目录注入
    assert "cmd.exe" in prompt                        # shell 自述
    assert "全新会话" in prompt and "cd 不会跨调用保留" in prompt
    assert "越界" in prompt                           # 文件工具边界


def test_env_hint_fallback_on_resolve_error(monkeypatch):
    def boom():
        raise RuntimeError("no root")
    monkeypatch.setattr(cc_workspace, "resolve_project_dir", boom)
    hint = claude_loop.env_hint()                     # 解析异常回落，不抛
    assert "当前工作目录" in hint


def test_pick_directory_non_windows(monkeypatch):
    monkeypatch.setattr(cc_workspace.os, "name", "posix")
    assert cc_workspace.pick_directory() == ""        # 非 Windows 无原生选择器，返回空


def test_pick_directory_strips_bom(monkeypatch, tmp_path):
    """2026-11-11 真机踩坑：旧 PowerShell 脚本带 BOM 写回目录选择结果——
    BOM 成路径首字符 → abspath 错拼 exe 目录 → 「目录不存在」"""
    import subprocess
    from types import SimpleNamespace
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(cc_workspace.os, "name", "nt")

    def fake_run(cmd, **k):
        (tmp_path / f"yuanai_pick_{os.getpid()}.txt").write_bytes(
            "﻿C:\\Users\\test\\repo".encode("utf-8"))

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert cc_workspace.pick_directory() == "C:\\Users\\test\\repo"  # BOM 已剥


def test_pick_directory_uses_bomless_encoding(monkeypatch, tmp_path):
    import subprocess
    from types import SimpleNamespace
    captured = {}
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(cc_workspace.os, "name", "nt")
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **k: captured.update(cmd=cmd) or SimpleNamespace())
    cc_workspace.pick_directory()
    assert "UTF8Encoding" in captured["cmd"][4]  # 改用无 BOM 编码写回
