# -*- coding: utf-8 -*-
"""联网搜索测试 — DDG/Bing 结果解析（monkeypatch 请求，零网络）

常规聊天联网（2026-10-15）：search_web 搜 URL → fetch_url + parse_html 取详情，
与数据采集链路共用 safe_fetch 咽喉。国内 DDG 不通 → Bing 回退。
运行：pytest test/test_web_search.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from yuanai_core.pure import web_search as ws  # noqa: E402


class FakeResult:
    def __init__(self, text):
        self.text = text
        self.status_code = 200


_DDG_HTML = """
<html><body>
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage1">结果一标题</a>
<a class="result__snippet">这是第一条结果的摘要</a>
<a class="result__a" href="https://example.com/page2">结果二标题</a>
<a class="result__snippet">第二条摘要</a>
<a class="result__a" href="/not-http">坏链接</a>
</body></html>
"""

_BING_HTML = """
<html><body>
<li class="b_algo"><h2><a href="https://zhuanlan.zhihu.com/p/1">知乎文章标题</a></h2>
  <div class="b_caption"><p>2025年10月 · 文章摘要内容</p></div></li>
<li class="b_algo"><h2><a href="https://example.org/b">另一个结果</a></h2>
  <p>另一段摘要</p></li>
</body></html>
"""


def test_ddg_parse(monkeypatch):
    monkeypatch.setattr(ws, "_fetch", lambda url, params: FakeResult(_DDG_HTML))
    r = ws._search_ddg("测试", 5)
    assert len(r) == 2
    assert r[0]["url"] == "https://example.com/page1"  # uddg 解码
    assert r[0]["snippet"] == "这是第一条结果的摘要"


def test_bing_parse(monkeypatch):
    monkeypatch.setattr(ws, "_fetch", lambda url, params: FakeResult(_BING_HTML))
    r = ws._search_bing("测试", 5)
    assert len(r) == 2
    assert r[0]["title"] == "知乎文章标题" and r[0]["url"].startswith("https://zhuanlan")
    assert "文章摘要内容" in r[0]["snippet"]


def test_web_search_fallback(monkeypatch):
    """DDG 异常 → Bing 回退；两者都失败 → []"""
    calls = []

    def fake(url, params):
        calls.append(url)
        if "duckduckgo" in url:
            raise OSError("被墙")
        return FakeResult(_BING_HTML)

    monkeypatch.setattr(ws, "_fetch", fake)
    r = ws.web_search("测试")
    assert len(r) == 2 and calls == [ws.SEARCH_BASE, "https://cn.bing.com/search"]

    monkeypatch.setattr(ws, "_fetch", lambda url, params: (_ for _ in ()).throw(OSError("down")))
    assert ws.web_search("测试") == []


def test_web_search_empty_query():
    assert ws.web_search("") == []
    assert ws.web_search("   ") == []


def test_format_results():
    assert "未找到" in ws.format_search_results([])
    out = ws.format_search_results([{"title": "T", "url": "https://x", "snippet": "S"}])
    assert "T" in out and "https://x" in out and "S" in out


def test_search_tool_category_general():
    from yuanai_core.tools import load_tools_for
    names = {t.name for t in load_tools_for("general")}
    assert "search_web" in names  # 常规聊天（simple_query/general_chat 都带 general）可用


if __name__ == "__main__":
    print("测试入口：pytest test/test_web_search.py -v")
