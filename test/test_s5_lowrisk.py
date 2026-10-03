# -*- coding: utf-8 -*-
"""S5 低危清理测试 — 冻结模式脚本白名单 / SVG 转义 / verify=False 移除

纯离线。运行：pytest test/test_s5_lowrisk.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')


# ---------------- L1：--run-script 白名单 ----------------

def test_run_script_allowed_matrix(tmp_path):
    from agent.tray import _run_script_allowed

    # 三个内置目录内的脚本 → 放行
    for rel in ("agent/datanalysis/scripts/描述性统计分析.py",
                "agent/datanalysis/crawl/通用网页采集.py",
                "skills/analysis/scripts/x.py"):
        assert _run_script_allowed(str(tmp_path / rel), str(tmp_path)), rel

    # 越界：项目根直下 / 系统目录 / 穿越 → 拒绝
    for rel in ("evil.py",
                "C:/Users/x/.ssh/evil.py",
                "agent/evil.py",
                "agent/datanalysis/evil.py"):
        assert not _run_script_allowed(str(tmp_path / rel), str(tmp_path)), rel
        assert not _run_script_allowed(rel, str(tmp_path)), rel

    # 穿越样式（含 .. 的路径 realpath 后落到白名单外）→ 拒绝
    assert not _run_script_allowed(str(tmp_path / "agent/datanalysis/scripts/../../evil.py"),
                                   str(tmp_path))


def test_run_script_allowed_realpath_traversal(tmp_path):
    """软链接逃逸：白名单目录内的链接指向外部文件 → realpath 后拒绝"""
    import os as _os
    from agent.tray import _run_script_allowed

    if not hasattr(_os, "symlink"):
        pytest.skip("当前环境不支持符号链接")
    outside = tmp_path / "outside.py"
    outside.write_text("print(1)", encoding="utf-8")
    link = tmp_path / "agent/datanalysis/scripts/innocent.py"
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        _os.symlink(outside, link)
        assert not _run_script_allowed(str(link), str(tmp_path))
    except OSError:
        pytest.skip("无权限创建符号链接")


# ---------------- L5：SVG 转义 ----------------

def test_esc_svg_escapes_quotes_and_angle_brackets():
    from api.v1.monitor.diagrams import _esc
    evil = '<script>"onload</script>'
    out = _esc(evil)
    assert "<" not in out and ">" not in out
    assert '"' not in out and "'" not in out
    assert "&lt;" in out and "&quot;" in out


def test_text_node_escapes_branch_name():
    """架构图分支名（git 外部可控）经 _text 转义后无法注入标签"""
    from api.v1.monitor.diagrams import _text
    out = _text(0, 0, "<script>alert('x')</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


# ---------------- L3：verify=False 已移除 ----------------

def test_no_verify_false_in_proxy_request():
    src = open(os.path.join(os.path.dirname(__file__), "..",
                            "spiderlx", "anti", "ip", "request_ip.py"),
               encoding="utf-8").read()
    # 只查 requests.get 的调用块（注释里会提到 verify 字样）
    call = src.split("requests.get")[1].split("raise_for_status")[0]
    assert "verify" not in call


# ---------------- L2：死代码已删除 ----------------

def test_db_trans_removed():
    assert not os.path.exists(os.path.join(os.path.dirname(__file__), "..", "db", "trans"))


if __name__ == "__main__":
    print("测试入口：pytest test/test_s5_lowrisk.py -v")
