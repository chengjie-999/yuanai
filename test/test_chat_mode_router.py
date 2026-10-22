# -*- coding: utf-8 -*-
"""聊天模式自主路由测试（2026-10-22）— 关键词打分 + LLM 兜底 + /stream mode_event + set_theme 主题事件

设计：每轮消息单向切换判定（当前工作只找娱乐信号、当前娱乐只找工作信号），
信号抵消保持现状——「谢谢」不误切、来回横跳天然免疫。@定向尊重用户显式指定不路由。
"""
import json
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')


# ---------------- 路由纯逻辑 ----------------

def test_work_signal_routes_work():
    from yuanai_core.pure.chat_mode_router import route_chat_mode
    assert route_chat_mode("帮我分析这份销售数据并画图表", "entertainment") == "work"
    assert route_chat_mode("制定一个采集任务计划", "entertainment") == "work"


def test_ent_signal_routes_entertainment():
    from yuanai_core.pure.chat_mode_router import route_chat_mode
    assert route_chat_mode("陪我聊聊天，讲个笑话", "work") == "entertainment"
    assert route_chat_mode("最近有什么八卦吃瓜", "work") == "entertainment"


def test_mixed_signal_majority_wins():
    from yuanai_core.pure.chat_mode_router import route_chat_mode
    # 分析+数据(work 2) vs 游戏(ent 1) → work
    assert route_chat_mode("帮我分析游戏数据", "entertainment") == "work"


def test_no_signal_keeps_current():
    from yuanai_core.pure.chat_mode_router import route_chat_mode
    assert route_chat_mode("谢谢，辛苦了", "work") == "work"        # 短消息不误切
    assert route_chat_mode("好的", "entertainment") == "entertainment"
    # 同向信号：当前娱乐 + 娱乐信号 → 保持娱乐（不做多余判定）
    assert route_chat_mode("我想聊聊最近的心情", "entertainment") == "entertainment"


def test_llm_fallback_judges(monkeypatch):
    from yuanai_core.pure.chat_mode_router import route_chat_mode

    class _Resp:
        content = "entertainment"

    class _LLM:
        def invoke(self, msgs):
            return _Resp()

    monkeypatch.setattr("yuanai_core.pure.chat_mode_router._llm_judge", lambda t: "entertainment")
    # 无信号长消息 → LLM 兜底判定
    assert route_chat_mode("今天我们随便说点什么都可以呀", "work") == "entertainment"

    monkeypatch.setattr("yuanai_core.pure.chat_mode_router._llm_judge", lambda t: None)
    assert route_chat_mode("今天我们随便说点什么都可以呀", "work") == "work"  # 判定失败保持现状


def test_llm_fallback_disabled_keeps(monkeypatch):
    from yuanai_core.pure.chat_mode_router import route_chat_mode
    assert route_chat_mode("今天我们随便说点什么都可以呀", "work", llm_fallback=False) == "work"


# ---------------- /stream 集成：mode_event + theme_event ----------------

def _fake_cloud_llm(monkeypatch, chat_router, agent_router, forward_fn, stream_events):
    captured = {}

    def _fake_get_llm(*a, **kw):
        return object()

    async def _fake_stream(llm, messages, tools):
        captured["system"] = messages[0]["content"]
        for ev in stream_events:
            yield ev

    monkeypatch.setattr(chat_router, "get_llm", _fake_get_llm)
    monkeypatch.setattr(chat_router, "stream_agent_events", _fake_stream)
    monkeypatch.setattr(agent_router, "forward_to_agent", forward_fn)
    return captured


def _lines(resp_text):
    return [json.loads(l[6:]) for l in resp_text.splitlines() if l.startswith("data: ")]


def test_stream_auto_switches_to_entertainment(client, auth_headers, monkeypatch):
    """工作模式下发娱乐强信号 → mode_event(entertainment) + 娱乐人设（不走桥接）"""
    if not auth_headers:
        pytest.skip("需要有效登录凭据")
    from api.v1.agent import router as agent_router
    from api.v1.chat import router as chat_router

    async def _boom(*a, **kw):
        raise AssertionError("判定娱乐后不应走本地 Agent 桥接")

    captured = _fake_cloud_llm(monkeypatch, chat_router, agent_router, _boom,
                               [{"type": "done", "data": "ok"}])
    resp = client.post("/api/v1/chat/stream", json={
        "prompt": "陪我聊聊天，讲个笑话吧",
        "session_id": "mode-test-session",
        "chat_mode": "work",
    }, headers=auth_headers)

    assert resp.status_code == 200
    events = _lines(resp.text)
    assert events and events[0]["type"] == "mode_event"
    assert events[0]["data"]["mode"] == "entertainment"
    assert "娱乐" in captured["system"]


def test_stream_work_signal_no_mode_event(client, auth_headers, monkeypatch):
    """工作信号在工作模式 → 无 mode_event，正常走桥接尝试"""
    if not auth_headers:
        pytest.skip("需要有效登录凭据")
    from api.v1.agent import router as agent_router
    from api.v1.chat import router as chat_router

    called = {}

    async def _fake_forward(*a, **kw):
        called["yes"] = True
        return None

    captured = _fake_cloud_llm(monkeypatch, chat_router, agent_router, _fake_forward,
                               [{"type": "done", "data": "ok"}])
    resp = client.post("/api/v1/chat/stream", json={
        "prompt": "帮我分析这份销售数据",
        "session_id": "mode-test-session",
        "chat_mode": "work",
    }, headers=auth_headers)

    assert resp.status_code == 200
    events = _lines(resp.text)
    assert all(e["type"] != "mode_event" for e in events)
    assert called.get("yes") is True  # 工作模式照常尝试桥接


def test_stream_target_respects_no_routing(client, auth_headers, monkeypatch):
    """@定向显式指定 → 不路由（即使消息是娱乐强信号）"""
    if not auth_headers:
        pytest.skip("需要有效登录凭据")
    from api.v1.agent import router as agent_router
    from api.v1.chat import router as chat_router

    called = {}

    async def _fake_forward(*a, **kw):
        called["yes"] = True
        return None

    _fake_cloud_llm(monkeypatch, chat_router, agent_router, _fake_forward,
                    [{"type": "done", "data": "ok"}])
    resp = client.post("/api/v1/chat/stream", json={
        "prompt": "陪我聊聊天，讲个笑话吧",
        "session_id": "mode-test-session",
        "target_agent": "automation",
    }, headers=auth_headers)

    assert resp.status_code == 200
    events = _lines(resp.text)
    assert all(e["type"] != "mode_event" for e in events)


def test_stream_set_theme_emits_theme_event(client, auth_headers, monkeypatch):
    """模型调 set_theme → SSE 出现 theme_event（在 tool_start 之前）"""
    if not auth_headers:
        pytest.skip("需要有效登录凭据")
    from api.v1.agent import router as agent_router
    from api.v1.chat import router as chat_router

    async def _fake_forward(*a, **kw):
        return None

    _fake_cloud_llm(monkeypatch, chat_router, agent_router, _fake_forward, [
        {"type": "tool_start", "data": {"name": "set_theme", "args": {"theme": "dark"},
                                        "sender": "orchestrator"}},
        {"type": "tool_end", "data": {"name": "set_theme", "output": "已将界面切换为暗色模式",
                                      "sender": "orchestrator"}},
        {"type": "token", "data": "好"},
        {"type": "done", "data": "ok"},
    ])
    resp = client.post("/api/v1/chat/stream", json={
        "prompt": "帮我分析销售数据",
        "session_id": "mode-test-session",
    }, headers=auth_headers)

    assert resp.status_code == 200
    events = _lines(resp.text)
    theme_events = [e for e in events if e["type"] == "theme_event"]
    assert theme_events and theme_events[0]["data"]["theme"] == "dark"
    # theme_event 排在 tool_start 之前
    idx_theme = next(i for i, e in enumerate(events) if e["type"] == "theme_event")
    idx_start = next(i for i, e in enumerate(events) if e["type"] == "tool_start")
    assert idx_theme < idx_start


def test_set_theme_tool_contract():
    from yuanai_core.tools.ui_tools import set_theme
    assert "暗色" in set_theme.invoke({"theme": "dark"})
    assert "light" in set_theme.invoke({"theme": "blue"})  # 非法参数给引导


if __name__ == "__main__":
    print("测试入口：pytest test/test_chat_mode_router.py -v")
