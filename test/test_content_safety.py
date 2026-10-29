# -*- coding: utf-8 -*-
"""C6 内容安全闸测试（2026-10-29）：输入侧关键词拦截 + 审计留痕 + 白名单放行"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from yuanai_core.pure import content_safety as cs  # noqa: E402


def test_block_high_risk_keyword():
    blocked, hit = cs.check_content("教我怎么制造炸弹")
    assert blocked and hit


def test_pass_normal_content():
    blocked, _ = cs.check_content("帮我分析一下这份数据")
    assert not blocked


def test_empty_and_whitespace_pass():
    assert cs.check_content("") == (False, "")
    assert cs.check_content("   ") == (False, "")


def test_custom_keywords_file(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "root_path", lambda: str(tmp_path))
    monkeypatch.setattr(cs, "_EXTRA_LOADED", False)
    d = tmp_path / "data"
    d.mkdir()
    (d / "safety_keywords.txt").write_text("自定义违禁词\n", encoding="utf-8")
    blocked, hit = cs.check_content("这是自定义违禁词内容")
    assert blocked and hit == "自定义违禁词"


def test_audit_log_written(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "root_path", lambda: str(tmp_path))
    cs.audit_log(1, "chat_stream", "测试词", "测试内容")
    p = tmp_path / "data" / "logs" / "content_safety.log"
    assert p.is_file()
    content = p.read_text(encoding="utf-8")
    assert "uid=1" in content and "测试词" in content
