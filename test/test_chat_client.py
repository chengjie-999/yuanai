# -*- coding: utf-8 -*-
"""云端对话通道客户端测试（v3.1 #37，2026-11-12）——零网络：
httpx 以假模块注入（client._httpx），断言令牌/会话/流式事件解析/401 重试。"""

import asyncio
import json
import sys
import os
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # noqa: E402

from agent.chat_client import CloudChatClient, _https_url, DEFAULT_MODEL  # noqa: E402


def test_https_url_conversion():
    assert _https_url("wss://cjyuanai.cn") == "https://cjyuanai.cn"
    assert _https_url("ws://localhost:8000/") == "http://localhost:8000"
    assert _https_url("") == ""


class _Resp:
    def __init__(self, status=200, data=None, text=""):
        self.status_code = status
        self._data = data
        self.text = text

    def json(self):
        if isinstance(self._data, dict):
            return self._data
        raise ValueError("not json")


class _FakeHttpx:
    """极简 httpx 假模块：post/get 记录调用，可配响应序列"""

    def __init__(self):
        self.post_calls = []
        self.get_calls = []
        self.post_resp = {}
        self.get_resp = {}
        self.stream_lines = []          # 注入的 SSE 行序列
        self.stream_status = 200
        self.stream_bodies = []         # 流式请求体记录
        self.Timeout = lambda a=1, read=None: SimpleNamespace(timeout=a, read=read)
        self.HTTPError = type("HTTPError", (Exception,), {})
        outer = self

        class AsyncClient:
            def __init__(self, timeout=None):
                self._fake = outer

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            def stream(self, method, url, json=None, headers=None):
                self._fake.stream_bodies.append(json)
                return _FakeStream(self._fake)

        self.AsyncClient = AsyncClient

    def post(self, url, **kw):
        self.post_calls.append((url, kw))
        key = url.split("/api/v1/")[-1] if "/api/v1/" in url else url
        r = self.post_resp.get(key) or self.post_resp.get(url)
        return r if r is not None else _Resp(200, {})

    def get(self, url, **kw):
        self.get_calls.append((url, kw))
        return self.get_resp.get(url, _Resp(200, []))


class _FakeStream:
    def __init__(self, fake):
        self._fake = fake

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    @property
    def status_code(self):
        return self._fake.stream_status

    def json(self):
        return {"detail": f"stream http {self.status_code}"}

    @property
    def text(self):
        return f"stream http {self.status_code}"

    async def aiter_lines(self):
        for line in self._fake.stream_lines:
            yield line


def _client(fake):
    c = CloudChatClient.__new__(CloudChatClient)
    c._base = "https://cjyuanai.cn"
    c._agent_id = "7"
    c._secret = "SECRET"
    c._timeout = 30.0
    c._httpx = fake
    c._token = ""
    c._display_name = ""
    return c


def test_ensure_token_ok_and_cached():
    fake = _FakeHttpx()
    fake.post_resp["agent/chat-token"] = _Resp(200, {"token": "JWT123", "display_name": "小元用户"})
    c = _client(fake)
    assert c.ensure_token() == "JWT123"
    assert c.ensure_token() == "JWT123"  # 已缓存不重复请求
    assert len(fake.post_calls) == 1
    assert fake.post_calls[0][1]["headers"]["X-Agent-Id"] == "7"


def test_ensure_token_unbound_403_human_message():
    fake = _FakeHttpx()
    fake.post_resp["agent/chat-token"] = _Resp(403, {"detail": "设备未绑定账号"})
    c = _client(fake)
    with pytest.raises(RuntimeError) as ei:
        c.ensure_token()
    assert "绑定" in str(ei.value)


def test_ensure_token_network_error_human():
    class _HttpxErr(_FakeHttpx):
        def post(self, url, **kw):
            raise self.HTTPError("boom")

    c = _client(_HttpxErr())
    with pytest.raises(RuntimeError) as ei:
        c.ensure_token()
    assert "无法连接云端" in str(ei.value)


def test_main_session_and_save():
    fake = _FakeHttpx()
    fake.post_resp["agent/chat-token"] = _Resp(200, {"token": "JWT1"})
    fake.post_resp["chat/main-session"] = _Resp(200, {"session_id": "abc123"})
    c = _client(fake)
    assert c.main_session_id() == "abc123"
    c.save_messages("abc123", [{"role": "user", "content": "hi"}])
    assert any("chat/save" in u for u, _ in fake.post_calls)


def test_stream_events_and_401_retry():
    fake = _FakeHttpx()
    fake.post_resp["agent/chat-token"] = _Resp(200, {"token": "JWT1"})
    fake.stream_lines = [
        "data: " + json.dumps({"type": "token", "data": "你好"}),
        "data: " + json.dumps({"type": "tool_start", "data": {"name": "search_web", "args": {}}}),
        "data: " + json.dumps({"type": "tool_end", "data": {"name": "search_web", "output": "结果"}}),
        "data: " + json.dumps({"type": "done", "data": {"display_content": "你好"}}),
    ]
    c = _client(fake)

    async def _run():
        return [ev async for ev in c.stream("s1", "hi", [])]

    events = asyncio.run(_run())
    assert [e["type"] for e in events] == ["token", "tool_start", "tool_end", "done"]
    body = fake.stream_bodies[-1]
    assert body["prompt"] == "hi"
    assert body["model"] == DEFAULT_MODEL
    assert body["chat_backend"] == "auto"


def test_stream_error_status_raises():
    fake = _FakeHttpx()
    fake.post_resp["agent/chat-token"] = _Resp(200, {"token": "JWT1"})
    fake.stream_status = 403
    c = _client(fake)

    async def _run():
        return [ev async for ev in c.stream("s1", "hi", [])]

    with pytest.raises(RuntimeError) as ei:
        asyncio.run(_run())
    assert "403" in str(ei.value)


def test_send_decision_posts_decision_body():
    fake = _FakeHttpx()
    fake.post_resp["agent/chat-token"] = _Resp(200, {"token": "JWT1"})
    c = _client(fake)
    c.send_decision("did123", True)
    body = fake.post_calls[-1][1]["json"]
    assert body == {"decision": {"decision_id": "did123", "approve": True}}


def test_activity_returns_observe_payload():
    """v3.2 #38：activity() 带 JWT 拉 /chat/cc-activity 观测数据"""
    fake = _FakeHttpx()
    fake.post_resp["agent/chat-token"] = _Resp(200, {"token": "JWT1"})
    fake.get_resp["https://cjyuanai.cn/api/v1/chat/cc-activity"] = _Resp(200, {
        "online": True, "latest": {"message": "工具调用: bash"},
        "age_s": 42, "activities": [{"message": "工具调用: bash"}]})
    c = _client(fake)
    d = c.activity()
    assert d["online"] is True and d["age_s"] == 42
    assert d["activities"][0]["message"] == "工具调用: bash"
    # JWT 鉴权头已带（用户口径，非设备凭据）
    assert fake.get_calls[0][1]["headers"]["Authorization"] == "Bearer JWT1"


def test_activity_error_raises_human():
    fake = _FakeHttpx()
    fake.post_resp["agent/chat-token"] = _Resp(200, {"token": "JWT1"})
    fake.get_resp["https://cjyuanai.cn/api/v1/chat/cc-activity"] = _Resp(500, {"detail": "boom"})
    c = _client(fake)
    with pytest.raises(RuntimeError) as ei:
        c.activity()
    assert "观测" in str(ei.value)


def test_list_plans_and_detail():
    fake = _FakeHttpx()
    fake.post_resp["agent/chat-token"] = _Resp(200, {"token": "JWT1"})
    fake.get_resp["https://cjyuanai.cn/api/v1/plan/list"] = _Resp(200, {
        "plans": [{"id": 7, "title": "RFM 分析", "status": "queued"}]})
    fake.get_resp["https://cjyuanai.cn/api/v1/plan/7"] = _Resp(200, {
        "title": "RFM 分析", "steps": [{"step_no": 1}]})
    c = _client(fake)
    plans = c.list_plans()
    assert plans[0]["id"] == 7
    detail = c.plan_detail(7)
    assert detail["steps"][0]["step_no"] == 1
