# -*- coding: utf-8 -*-
"""DSML 工具调用标记抑制测试 — 整段剥离 / 跨 chunk 状态机 / 零误伤

运行：pytest test/test_dsml_filter.py -v（纯离线）
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from yuanai_core.pure.dsml import strip_dsml, has_dsml, DsmlStreamFilter  # noqa: E402

# 实测泄漏形态（全角竖线）
_SAMPLE = ("回答你之前，我先搜索一下：<｜｜DSML｜｜tool_calls>"
           '<｜｜DSML｜｜invoke name="search_web">'
           '<｜｜DSML｜｜parameter name="query" string="true">AI大模型 最新动态</｜｜DSML｜｜parameter>'
           "</｜｜DSML｜｜invoke></｜｜DSML｜｜tool_calls> 搜索完成。")

_ASCII_SAMPLE = ("pre <||DSML||tool_calls><||DSML||invoke name=\"x\">"
                 "</||DSML||invoke></||DSML||tool_calls> post")


def test_has_dsml():
    assert has_dsml(_SAMPLE) is True
    assert has_dsml("普通文本没有标记") is False
    assert has_dsml("markdown 表格 | a | b |") is False


def test_strip_dsml_whole():
    out = strip_dsml(_SAMPLE)
    assert "DSML" not in out
    assert "回答你之前" in out and "搜索完成" in out
    assert strip_dsml(_ASCII_SAMPLE) == "pre  post"


def test_stream_filter_whole_chunk():
    f = DsmlStreamFilter()
    out = f.feed(_SAMPLE) + f.flush()
    assert "DSML" not in out
    assert out == strip_dsml(_SAMPLE)


def test_stream_filter_char_by_char():
    """1 字符一 chunk 逐个喂入，结果与整段剥离等价（覆盖 < / <｜ / <｜｜DS 三处切点）"""
    f = DsmlStreamFilter()
    out = ""
    for ch in _SAMPLE:
        out += f.feed(ch)
    out += f.flush()
    assert "DSML" not in out
    assert out == strip_dsml(_SAMPLE)


def test_stream_filter_mixed_with_normal_text():
    """DSML 块前后正常文本零改动；中文/标点不受影响"""
    f = DsmlStreamFilter()
    text = "第一部分。" + _SAMPLE + "中间段落。" + _SAMPLE + "结尾。"
    out = ""
    for ch in text:
        out += f.feed(ch)
    out += f.flush()
    assert "DSML" not in out
    assert "第一部分" in out and "中间段落" in out and "结尾" in out


def test_stream_filter_no_dsml_unchanged():
    """无 DSML 的普通文本零改动（含 markdown 表格竖线）"""
    f = DsmlStreamFilter()
    text = "| 列A | 列B |\n|---|---|\n| 1 | 2 |\n这是一段普通回复，包含 | 竖线。"
    out = ""
    for ch in text:
        out += f.feed(ch)
    out += f.flush()
    assert out == text


def test_stream_filter_unclosed_block_flushed_away():
    """流末仍在 BLOCK 态：剩余缓冲全部丢弃（宁缺勿漏）"""
    f = DsmlStreamFilter()
    out = f.feed("正文开头。") + f.feed("<｜｜DSML｜｜tool_calls>") + f.feed('<｜｜DSML｜｜invoke name="x">')
    out += f.flush()
    assert "DSML" not in out
    assert out == "正文开头。"


def test_stream_filter_saw_block_flag():
    f = DsmlStreamFilter()
    f.feed("<｜｜DSML｜｜tool_calls></｜｜DSML｜｜tool_calls>")
    f.flush()
    assert f.saw_block is True
    f2 = DsmlStreamFilter()
    f2.feed("普通文本")
    f2.flush()
    assert f2.saw_block is False


def test_ascii_pipe_variant_stream():
    f = DsmlStreamFilter()
    out = f.feed(_ASCII_SAMPLE) + f.flush()
    assert "DSML" not in out
    assert out == "pre  post"


if __name__ == "__main__":
    print("测试入口：pytest test/test_dsml_filter.py -v")
