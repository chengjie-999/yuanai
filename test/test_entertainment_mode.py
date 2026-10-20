# -*- coding: utf-8 -*-
"""娱乐模式（E1）：chat_mode=entertainment 强制云端直连——跳过本地 Agent 桥接、
使用专属娱乐人设提示（非回退提示）、忽略 @定向；工作模式不受影响。"""

import pytest


def _fake_cloud_llm(monkeypatch, chat_router, agent_router, forward_fn):
    """公共 mock：截获 system prompt；forward_to_agent 行为由 forward_fn 决定"""
    captured = {}

    def _fake_get_llm(*a, **kw):
        return object()

    async def _fake_stream(llm, messages, tools):
        captured["system"] = messages[0]["content"]
        yield {"type": "done", "data": "e1-ok"}

    monkeypatch.setattr(chat_router, "get_llm", _fake_get_llm)
    monkeypatch.setattr(chat_router, "stream_agent_events", _fake_stream)
    monkeypatch.setattr(agent_router, "forward_to_agent", forward_fn)
    return captured


class TestEntertainmentMode:

    def test_entertainment_skips_bridge_and_uses_persona(self, client, auth_headers, monkeypatch):
        """娱乐模式：不调 forward_to_agent、人设提示含「娱乐」、非回退提示、忽略 @定向"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        from api.v1.agent import router as agent_router
        from api.v1.chat import router as chat_router

        async def _boom(*a, **kw):
            raise AssertionError("娱乐模式不应走本地 Agent 桥接")

        captured = _fake_cloud_llm(monkeypatch, chat_router, agent_router, _boom)

        resp = client.post("/api/v1/chat/stream", json={
            "prompt": "你好，陪我聊聊天",
            "session_id": "e1-test-session",
            "chat_mode": "entertainment",
            # 娱乐模式不委派：即使带了 @定向 也忽略（提示不含角色切换）
            "target_agent": "automation",
        }, headers=auth_headers)

        assert resp.status_code == 200
        assert "e1-ok" in resp.text
        sys_prompt = captured["system"]
        assert "娱乐" in sys_prompt
        assert "本地智能体离线" not in sys_prompt  # 专属人设 ≠ 云端回退提示
        assert "自动化智能体" not in sys_prompt  # @定向在娱乐模式被忽略

    def test_work_mode_still_bridges(self, client, auth_headers, monkeypatch):
        """工作模式（默认）：仍走桥接分支，离线时用回退提示（对照基准）"""
        if not auth_headers:
            pytest.skip("需要有效登录凭据")
        from api.v1.agent import router as agent_router
        from api.v1.chat import router as chat_router

        called = {}

        async def _fake_forward(*a, **kw):
            called["yes"] = True
            return None  # 无在线 Agent → 云端回退

        captured = _fake_cloud_llm(monkeypatch, chat_router, agent_router, _fake_forward)

        resp = client.post("/api/v1/chat/stream", json={
            "prompt": "你好",
            "session_id": "e1-test-session",
        }, headers=auth_headers)

        assert resp.status_code == 200
        assert called.get("yes") is True  # 工作模式走桥接尝试
        assert "本地智能体离线" in captured["system"]  # 回退提示（旧行为不变）
