# -*- coding: utf-8 -*-
"""计划工具双路径测试 — mock HTTP / mock db（无 MySQL 依赖）

- 本地 Agent 进程（_memory_path=http）→ _agent_http 收到 POST /plan/xxx
- 云端进程（direct）→ 调 store/db 方法；校验失败返回可读错误
运行：pytest test/test_plan_tools.py -v
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from yuanai_core.tools import plan_tools as pt  # noqa: E402


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(pt, "current_user_id", _Ctx(3))
    monkeypatch.setattr(pt, "current_session_id", _Ctx("sess-1"))
    pt._last_calls.clear()  # 同参 30s 合并缓存隔离测试间串扰


class _Ctx:
    def __init__(self, v):
        self._v = v

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


def test_create_plan_http_path(monkeypatch):
    """本地 Agent：走 HTTP POST /plan/create，带 session_id 与解析后的步骤"""
    monkeypatch.setattr(pt, "_memory_path", lambda: "http")
    calls = []

    class _Resp:
        def __init__(self, payload):
            self._b = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        def read(self):
            return self._b

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_open(req, timeout=None):
        calls.append((req.full_url, req.get_method(), req.data))
        return _Resp({"ok": True, "plan_id": 7})

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    out = pt.create_plan.invoke({"title": "抓数据", "goal": "先抓再分析",
        "steps": json.dumps([{"skill": "collection", "desc": "抓取网页", "params": {}}])})
    assert "计划 #7" in out and "草稿" in out
    url, method, body = calls[0]
    data = json.loads(body.decode("utf-8"))
    assert "/plan/create" in url and method == "POST"
    assert data["session_id"] == "sess-1" and data["steps"][0]["skill"] == "collection"


def test_create_plan_validation_error(monkeypatch):
    monkeypatch.setattr(pt, "_memory_path", lambda: "http")
    out = pt.create_plan.invoke({"title": "x", "goal": "y", "steps": "不是 JSON"})
    assert "步骤不合法" in out
    out2 = pt.create_plan.invoke({"title": "x", "goal": "y",
        "steps": json.dumps([{"skill": "automation", "desc": "开浏览器"}])})
    assert "skill" in out2


def test_execute_plan_http_path(monkeypatch):
    monkeypatch.setattr(pt, "_memory_path", lambda: "http")
    calls = []

    class _Resp:
        def __init__(self, payload):
            self._b = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        def read(self):
            return self._b

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_open(req, timeout=None):
        calls.append((req.full_url, req.get_method(), req.data))
        return _Resp({"ok": True, "already": False, "agent_online": True})

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    out = pt.execute_plan.invoke({"plan_id": 5})
    assert "加入队列" in out
    data = json.loads(calls[0][2].decode("utf-8"))
    assert data["plan_id"] == 5


def test_execute_plan_offline_hint(monkeypatch):
    monkeypatch.setattr(pt, "_memory_path", lambda: "http")

    class _Resp:
        def __init__(self, payload):
            self._b = json.dumps({"ok": True, "already": False, "agent_online": False},
                                 ensure_ascii=False).encode("utf-8")

        def read(self):
            return self._b

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: _Resp({"ok": True, "already": False,
                                                         "agent_online": False}))
    out = pt.execute_plan.invoke({"plan_id": 5})
    assert "未连接" in out or "Agent" in out


def test_intent_classifier_plan_priority():
    """回归：「制定计划先抓取再分析」曾被 data_task 高分抢走 → 计划工具未加载"""
    from agent.intent_classifier import classifier
    for msg in [
        '帮我制定一个计划：先抓取 https://example.com 的页面内容，再做描述性统计分析和图表',
        '执行我的计划', '看看计划进度',
    ]:
        assert classifier.classify(msg).group == 'plan_task', msg
    # 不带计划语义的请求不受影响
    assert classifier.classify('帮我分析这个数据集').group == 'data_task'
    assert classifier.classify('抓取这个网页的数据').group == 'crawl_task'
    assert classifier.classify('你好').group == 'general_chat'


def test_plan_call_direct_path(monkeypatch):
    """云端进程直连：校验失败返回可读错误（先过身份、再被步骤校验拦截）"""
    monkeypatch.setattr(pt, "current_user_id", _Ctx(0))
    out = pt._plan_call_direct("/create", {"user_id": 0, "title": "x", "goal": "", "steps": []})
    assert out["ok"] is False and "用户身份" in out["detail"]
    monkeypatch.setattr(pt, "current_user_id", _Ctx(3))
    out2 = pt._plan_call_direct("/create", {"user_id": 3, "title": "x", "goal": "", "steps": []})
    assert out2["ok"] is False and "步骤" in out2["detail"]


if __name__ == "__main__":
    print("测试入口：pytest test/test_plan_tools.py -v")
