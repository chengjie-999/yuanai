"""N3 云端/本地三态切换测试（2026-11-06）

覆盖：route_chat_backend 关键词路由（cloud/local/auto/抵消保持）；
/stream cloud 跳过桥接、local 离线报错不回退、用户命令发 backend_event；
set_chat_backend 工具拦截 → backend_event。
"""
import json

import pytest

from yuanai_core.pure.chat_mode_router import route_chat_backend


# ---------------- 关键词路由 ----------------

def test_route_chat_backend_signals():
    assert route_chat_backend("切到云端", "auto") == "cloud"
    assert route_chat_backend("以后都用云端模式", "local") == "cloud"
    assert route_chat_backend("用我的电脑执行", "auto") == "local"
    assert route_chat_backend("本地模式跑这个分析", "cloud") == "local"
    assert route_chat_backend("恢复自动", "cloud") == "auto"
    assert route_chat_backend("谢谢你", "auto") == "auto"          # 无信号保持
    assert route_chat_backend("用我电脑还是用云端好？", "auto") == "auto"  # 双信号抵消保持
    assert route_chat_backend("", "cloud") == "cloud"              # 空消息保持


def test_route_chat_backend_one_way_no_flip():
    """信号抵消/弱信号不回横跳（同 chat_mode 单向语义）"""
    assert route_chat_backend("帮我分析数据", "local") == "local"  # 无关信号不影响


# ---------------- /stream 三态 ----------------

def _lines(resp_text):
    return [json.loads(l[6:]) for l in resp_text.splitlines() if l.startswith("data: ")]


def _setup_fake(monkeypatch, chat_router, agent_router, forward_behavior, events):
    """monkeypatch get_llm/stream_agent_events/forward_to_agent（同娱乐模式测试套路）"""
    captured = {}

    def _fake_get_llm(*a, **kw):
        return object()

    async def _fake_stream(llm, messages, tools, **kwargs):
        captured["system"] = messages[0]["content"]
        for ev in events:
            yield ev

    monkeypatch.setattr(chat_router, "get_llm", _fake_get_llm)
    monkeypatch.setattr(chat_router, "stream_agent_events", _fake_stream)
    monkeypatch.setattr(agent_router, "forward_to_agent", forward_behavior)
    return captured


def _forward_ok(*a, **k):
    async def _f():
        return "req-1"
    return _f()


def test_stream_local_mode_offline_errors_no_fallback(client, auth_headers, monkeypatch):
    """local 模式 + Agent 离线 → SSE error 事件，不回退云端"""
    if not auth_headers:
        pytest.skip("需要有效登录凭据")
    from api.v1.agent import router as agent_router
    from api.v1.chat import router as chat_router

    async def _forward_none(*a, **k):
        return None

    _setup_fake(monkeypatch, chat_router, agent_router, _forward_none, [])
    resp = client.post("/api/v1/chat/stream", json={
        "model": "deepseek-flash", "prompt": "测试", "history": [],
        "system_prompt": "x", "session_id": "s_n3", "chat_backend": "local",
    }, headers=auth_headers)
    assert resp.status_code == 200
    events = _lines(resp.text)
    assert any(e["type"] == "error" for e in events)
    err = next(e for e in events if e["type"] == "error")
    assert "本地模式" in err["data"]


def test_stream_cloud_mode_skips_bridge(client, auth_headers, monkeypatch):
    """cloud 模式 → 不调 forward_to_agent，直接云端直连"""
    if not auth_headers:
        pytest.skip("需要有效登录凭据")
    from api.v1.agent import router as agent_router
    from api.v1.chat import router as chat_router

    called = {"n": 0}

    async def _forward(*a, **k):
        called["n"] += 1
        return "req-1"

    _setup_fake(monkeypatch, chat_router, agent_router, _forward,
                [{"type": "done", "data": {}}])
    resp = client.post("/api/v1/chat/stream", json={
        "model": "deepseek-flash", "prompt": "测试", "history": [],
        "system_prompt": "x", "session_id": "s_n3c", "chat_backend": "cloud",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert called["n"] == 0  # 桥接被跳过


def test_stream_user_command_emits_backend_event(client, auth_headers, monkeypatch):
    """用户命令「切到云端」→ backend_event 首发（cloud 模式且跳过桥接）"""
    if not auth_headers:
        pytest.skip("需要有效登录凭据")
    from api.v1.agent import router as agent_router
    from api.v1.chat import router as chat_router

    _setup_fake(monkeypatch, chat_router, agent_router, _forward_ok,
                [{"type": "done", "data": {}}])
    resp = client.post("/api/v1/chat/stream", json={
        "model": "deepseek-flash", "prompt": "切到云端", "history": [],
        "system_prompt": "x", "session_id": "s_n3e", "chat_backend": "auto",
    }, headers=auth_headers)
    events = _lines(resp.text)
    assert any(e["type"] == "backend_event" and e["data"]["backend"] == "cloud"
               for e in events)


# ---------------- set_chat_backend 工具拦截 ----------------

def test_ui_events_set_chat_backend():
    from api.v1.chat.router import _ui_events
    ev = {"type": "tool_start",
          "data": {"name": "set_chat_backend", "args": {"backend": "local"}}}
    out = _ui_events(ev)
    assert out == [{"type": "backend_event", "data": {"backend": "local"}}]
    # 非法值不触发
    ev2 = {"type": "tool_start",
           "data": {"name": "set_chat_backend", "args": {"backend": "nope"}}}
    assert _ui_events(ev2) == []
    # set_theme 不受影响
    ev3 = {"type": "tool_start",
           "data": {"name": "set_theme", "args": {"theme": "dark"}}}
    assert _ui_events(ev3)[0]["type"] == "theme_event"


def test_set_chat_backend_tool_registered():
    from yuanai_core.tools import all_tools
    tool = next((t for t in all_tools if t.name == "set_chat_backend"), None)
    assert tool is not None
    out = tool.invoke({"backend": "local"})
    assert "本机" in str(out)


if __name__ == "__main__":
    print("测试入口：pytest test/test_chat_backend.py -v")
