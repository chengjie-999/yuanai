# -*- coding: utf-8 -*-
"""P1-6 CC 读自家分享链接测试 — 链接检测/展开注入/不可读人话提示（零网络）

运行：pytest test/test_share_link_expand.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # noqa: E402
sys.stdout.reconfigure(encoding='utf-8')

from api.v1.chat.router import _expand_share_links  # noqa: E402
from api.v1.chat import share as share_mod  # noqa: E402


@pytest.fixture
def shares_dir(tmp_path, monkeypatch):
    """把分享文件目录指到隔离 tmp（写入两份测试分享页）"""
    monkeypatch.setattr(share_mod, "_share_path",
                        lambda sid: str(tmp_path / f"{sid}.html"))
    (tmp_path / "abc12345.html").write_text(
        "<html><body><div class='bubble'>你好，这是分享正文</div>"
        "<footer>内容由 AI 生成</footer></body></html>", encoding="utf-8")
    return tmp_path


def test_absolute_link_expanded(shares_dir):
    out = _expand_share_links("帮我总结这个分享 https://cjyuanai.cn/api/v1/share/abc12345 的内容")
    assert "【分享内容已展开（abc12345）" in out
    assert "你好，这是分享正文" in out
    assert "https://cjyuanai.cn/api/v1/share/abc12345" in out  # 原链接保留


def test_relative_link_expanded(shares_dir):
    out = _expand_share_links("看一下 /api/v1/share/abc12345")
    assert "【分享内容已展开（abc12345）" in out


def test_unreadable_link_human_hint(shares_dir):
    out = _expand_share_links("读一下 https://cjyuanai.cn/api/v1/share/doesnot42")
    assert "无法读取（未分享或已取消）" in out
    assert "doesnot42" in out


def test_non_share_links_untouched(shares_dir):
    prompt = "先看 https://cjyuanai.cn/api/v1/share/abc12345 再看 https://example.com/x"
    out = _expand_share_links(prompt)
    assert "【分享内容已展开" in out          # 自家链接展开
    assert "https://example.com/x" in out      # 外链原样保留


def test_same_link_expanded_once(shares_dir):
    prompt = ("https://cjyuanai.cn/api/v1/share/abc12345 "
              "和 /api/v1/share/abc12345 各来一遍")
    out = _expand_share_links(prompt)
    assert out.count("【分享内容已展开") == 1  # 同 sid 只展开一次
