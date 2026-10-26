# -*- coding: utf-8 -*-
"""SSE 序列化清洗测试（B4 回复中途截断根因，2026-10-26）

网关流脏字节产生孤立 surrogate：json.dumps(ensure_ascii=False) 的字符串含
surrogate 时 uvicorn utf-8 编码抛 UnicodeEncodeError → SSE 流当场中断 =
回复中途截断。_sse 序列化前递归清洗。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.v1.chat.router import _sse  # noqa: E402


def test_sse_cleans_surrogate_in_string():
    dirty = "你好" + chr(0xdc80) + "世界"
    out = _sse({"type": "token", "data": dirty})
    assert chr(0xdc80) not in out
    assert out.encode("utf-8")  # 可严格编码（旧实现此处抛 UnicodeEncodeError）
    assert "你好" in out and "世界" in out


def test_sse_cleans_nested_structures():
    out = _sse({"data": {"hits": ["a" + chr(0xdc80), {"x": chr(0xdc81)}]}})
    assert chr(0xdc80) not in out and chr(0xdc81) not in out
    out.encode("utf-8")


def test_sse_passes_clean_content_through():
    out = _sse({"type": "done", "data": {"display_content": "正常回答"}})
    assert '"正常回答"' in out
    import json
    assert json.loads(out)["data"]["display_content"] == "正常回答"
