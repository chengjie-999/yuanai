# -*- coding: utf-8 -*-
"""联网搜索测试 — 解析/清洗/去重/域名标注/答案卡/短 query 防御（零网络）

业内常规对齐（2026-10-15）：Bing 国内站主用、DDG 海外兜底；结果带来源
域名、同域去重、摘要去日期前缀、答案卡；on_tool_end 输出归一化（ToolMessage
外壳 content='...' 曾泄漏）。
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
<a class="result__a" href="https://example.org/page2">结果二标题</a>
<a class="result__snippet">第二条摘要</a>
</body></html>
"""

_BING_HTML = """
<html><body>
<div class="b_ans">大模型是人工智能领域的重要发展方向。</div>
<li class="b_algo"><h2><a href="https://zhuanlan.zhihu.com/p/1">知乎文章标题</a></h2>
  <div class="b_caption"><p>2025年10月29日 · 文章摘要内容</p></div></li>
<li class="b_algo"><h2><a href="https://zhuanlan.zhihu.com/p/2">同域第二条</a></h2>
  <p>应被同域去重</p></li>
<li class="b_algo"><h2><a href="https://example.org/b">另一个结果</a></h2>
  <p>另一段摘要</p></li>
</body></html>
"""


def test_ddg_parse(monkeypatch):
    monkeypatch.setattr(ws, "_fetch", lambda url, params: FakeResult(_DDG_HTML))
    r = ws._search_ddg("测试", 5)
    assert len(r) == 2
    assert r[0]["url"] == "https://example.com/page1"  # uddg 解码


def test_bing_parse_answer_card_and_date_strip(monkeypatch):
    monkeypatch.setattr(ws, "_fetch", lambda url, params: FakeResult(_BING_HTML))
    r = ws._search_bing("测试", 8)
    assert r[0]["answer"] is True and "大模型" in r[0]["snippet"]
    assert r[1]["title"] == "知乎文章标题"
    assert r[1]["snippet"].startswith("文章摘要")  # 日期前缀已剥
    assert not r[1]["snippet"].startswith("2025年")


def test_web_search_bing_first(monkeypatch):
    """Bing 主用：成功时不触达 DDG"""
    calls = []

    def fake(url, params):
        calls.append(url)
        return FakeResult(_BING_HTML)

    monkeypatch.setattr(ws, "_fetch", fake)
    r = ws.web_search("最新 AI 大模型")
    assert calls == ["https://cn.bing.com/search"]
    assert any(x["title"] == "知乎文章标题" for x in r)


def test_web_search_ddg_fallback(monkeypatch):
    """Bing 异常 → DDG 兜底"""

    def fake(url, params):
        if "bing" in url:
            raise OSError("挂了")
        return FakeResult(_DDG_HTML)

    monkeypatch.setattr(ws, "_fetch", fake)
    r = ws.web_search("测试")
    assert len(r) == 2


def test_dedup_domains(monkeypatch):
    """同域去重：知乎两条只留首条"""
    monkeypatch.setattr(ws, "_fetch", lambda url, params: FakeResult(_BING_HTML))
    r = ws.web_search("测试")
    zhihu = [x for x in r if "zhihu" in x["url"]]
    assert len(zhihu) == 1
    assert any(x["url"] == "https://example.org/b" for x in r)


def test_short_query_rejected():
    assert ws.web_search("大") == []      # 单字直接空（曾搜「大」跑偏）
    assert ws.web_search("") == []
    from yuanai_core.tools.web_search import search_web
    out = search_web.invoke({"query": "大"})
    assert "过短" in out and "完整问题" in out


def test_format_results_with_domain():
    out = ws.format_search_results([{"title": "T", "url": "https://www.zhihu.com/p/1", "snippet": "S"}])
    assert "[T](https://www.zhihu.com/p/1) — zhihu.com" in out
    assert ws.format_search_results([]).startswith("未找到")


def test_tool_output_str_normalization():
    """on_tool_end 输出归一化：ToolMessage 外壳 content='...' 不泄漏"""
    from yuanai_core.core.chat import _tool_output_str

    class FakeToolMsg:
        content = "纯文本结果"

    assert _tool_output_str(FakeToolMsg()) == "纯文本结果"
    assert _tool_output_str("普通字符串") == "普通字符串"
    assert _tool_output_str(None) == ""

    class FakeListMsg:
        content = [{"type": "text", "text": "A"}, {"type": "text", "text": "B"}]

    assert _tool_output_str(FakeListMsg()) == "A\nB"


def test_search_tool_category_general():
    from yuanai_core.tools import load_tools_for
    names = {t.name for t in load_tools_for("general")}
    assert "search_web" in names


if __name__ == "__main__":
    print("测试入口：pytest test/test_web_search.py -v")
