"""免输码链路（安装器衔接）单测（2026-11-07）

覆盖：install_code.txt 读/清（优先级第一顺位）；setup 安装器文件名解析；
bootstrap 改名复制前把码带进数据根（免输码过引导不丢码）。
"""

import pytest

from agent.main import (install_code_from_exe_name, install_code_from_file,
                        clear_install_code_file)


def test_install_code_from_exe_name_setup_variant():
    """安装器文件名（setup 前缀）也能解析出码"""
    import sys
    old_exe, old_argv = getattr(sys, "executable", None), list(sys.argv)
    try:
        sys.executable = r"C:\tmp\yuanai-agent-setup-v20261107_YUAN-ABCD-1234-5678.exe"
        sys.argv = [sys.executable]
        assert install_code_from_exe_name() == "YUAN-ABCD-1234-5678"
        # 无码文件名 → 空
        sys.executable = r"C:\tmp\yuanai-agent-setup-v20261107.exe"
        sys.argv = [sys.executable]
        assert install_code_from_exe_name() == ""
    finally:
        sys.executable = old_exe
        sys.argv = old_argv


def test_install_code_from_file(tmp_path, monkeypatch):
    """读码文件：合法读回；非法/缺失静默返回空"""
    import agent.main as am
    monkeypatch.setattr(am, "_install_code_file", lambda: str(tmp_path / "code.txt"))

    # 缺失 → 空
    assert install_code_from_file() == ""

    # 合法（含换行/小写容错）
    (tmp_path / "code.txt").write_text("yuan-abcd-1234-5678\n", encoding="utf-8")
    assert install_code_from_file() == "YUAN-ABCD-1234-5678"

    # 非法（坏文件/乱写）→ 空（防注入）
    (tmp_path / "code.txt").write_text("rm -rf /", encoding="utf-8")
    assert install_code_from_file() == ""


def test_clear_install_code_file(tmp_path, monkeypatch):
    """注册成功后清码（一次消费）；不存在时静默"""
    import agent.main as am
    p = tmp_path / "code.txt"
    monkeypatch.setattr(am, "_install_code_file", lambda: str(p))
    p.write_text("YUAN-ABCD-1234-5678", encoding="utf-8")
    clear_install_code_file()
    assert not p.exists()
    clear_install_code_file()  # 不存在不抛


def test_bootstrap_carries_code(tmp_path, monkeypatch):
    """bootstrap 改名复制前把 exe 文件名里的码写进数据根（不覆盖已有）"""
    import agent.bootstrap as bs
    import agent.main as am
    target = tmp_path / "install_code.txt"
    # 数据根 patch：bs 的 frozen_data_root 是函数内 import 的，改 data_path 源头
    import utils.data_path as dp
    monkeypatch.setattr(dp, "frozen_data_root", lambda: str(tmp_path))

    # 无码 → 不写
    monkeypatch.setattr(am, "install_code_from_exe_name", lambda: "")
    bs._carry_install_code()
    assert not target.exists()

    # 有码 → 写入
    monkeypatch.setattr(am, "install_code_from_exe_name",
                        lambda: "YUAN-ABCD-1234-5678")
    bs._carry_install_code()
    assert target.read_text(encoding="utf-8") == "YUAN-ABCD-1234-5678"

    # 已有码文件 → 不覆盖（保留现有码）
    target.write_text("YUAN-EXIST-0000-0000", encoding="utf-8")
    bs._carry_install_code()
    assert target.read_text(encoding="utf-8") == "YUAN-EXIST-0000-0000"
