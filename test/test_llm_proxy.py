"""T5 LLM 云端代理测试（2026-11-06）

覆盖：设备凭据鉴权 / 未绑定 403 / 模型白名单 / 欠费 403 / 流式透传 + 统一
记账 / 非流式转发 + 记账 / Agent 端 lc 代理回退（identity 解析 ws→http）。
"""
import json
import secrets

import pytest

from api.v1.agent import llm_proxy
from db.session import get_db


def _db_or_skip():
    try:
        return get_db()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


@pytest.fixture(scope="module")
def db():
    return _db_or_skip()


@pytest.fixture()
def bound_device(db):
    """绑定到测试用户的设备（agent_secret 已知）→ 返回 (agent_id, secret)"""
    from db.session import AgentDevice, User
    uid = None
    with db.session() as sess:
        u = sess.query(User).filter_by(username="__test_api_user__").first()
        if u is None:
            r = db.register_user("__test_api_user__", "test1234")
            u = sess.query(User).filter_by(id=r["id"]).first()
        uid = u.id
    secret = secrets.token_hex(16)
    with db.session() as sess:
        dev = AgentDevice(user_id=uid, enabled=1,
                          install_code=f"LLM{secrets.token_hex(4).upper()}",
                          agent_secret=secret)
        sess.add(dev)
        sess.commit()
        dev_id = dev.id
    yield {"id": dev_id, "secret": secret, "uid": uid}
    with db.session() as sess:
        dev = sess.query(AgentDevice).filter_by(id=dev_id).first()
        if dev:
            sess.delete(dev)
            sess.commit()


def _h(dev):
    return {"X-Agent-Id": str(dev["id"]), "X-Agent-Secret": dev["secret"],
            "Content-Type": "application/json"}


def _body(**kw):
    b = {"model": "deepseek-flash", "messages": [{"role": "user", "content": "hi"}]}
    b.update(kw)
    return b


# ---------------- 鉴权 / 白名单 / 欠费 ----------------

def test_llm_proxy_requires_device_credential(client, bound_device):
    r = client.post("/api/v1/agent/llm/chat/completions", json=_body())
    assert r.status_code == 401
    bad = dict(_h(bound_device))
    bad["X-Agent-Secret"] = "wrong"
    r2 = client.post("/api/v1/agent/llm/chat/completions", json=_body(), headers=bad)
    assert r2.status_code == 401


def test_llm_proxy_unbound_device_403(client, db):
    from db.session import AgentDevice
    secret = secrets.token_hex(16)
    with db.session() as sess:
        dev = AgentDevice(user_id=None, enabled=1,
                          install_code=f"LLMU{secrets.token_hex(3).upper()}",
                          agent_secret=secret)
        sess.add(dev)
        sess.commit()
        dev_id = dev.id
    try:
        r = client.post("/api/v1/agent/llm/chat/completions", json=_body(),
                        headers={"X-Agent-Id": str(dev_id), "X-Agent-Secret": secret})
        assert r.status_code == 403
    finally:
        with db.session() as sess:
            dev = sess.query(AgentDevice).filter_by(id=dev_id).first()
            if dev:
                sess.delete(dev)
                sess.commit()


def test_llm_proxy_model_whitelist(client, bound_device):
    r = client.post("/api/v1/agent/llm/chat/completions",
                    json=_body(model="gpt-999-ultra"), headers=_h(bound_device))
    assert r.status_code == 403
    assert "白名单" in r.json()["detail"]


def test_llm_proxy_arrears_403(client, bound_device, monkeypatch):
    from api.v1.chat import router as chat_router
    monkeypatch.setattr(chat_router, "_check_arrears", lambda uid: "账户欠费")
    r = client.post("/api/v1/agent/llm/chat/completions",
                    json=_body(), headers=_h(bound_device))
    assert r.status_code == 403
    assert "欠费" in r.json()["detail"]


# ---------------- 转发与记账 ----------------

class _FakeResponse:
    def __init__(self, data):
        self._data = data

    @property
    def status_code(self):
        return 200

    @property
    def text(self):
        return json.dumps(self._data)

    def json(self):
        return self._data


class _FakeStreamCtx:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    @property
    def status_code(self):
        return 200

    def aiter_lines(self):
        async def _gen():
            for l in self._lines:
                yield l
        return _gen()

    async def aread(self):
        return b""


class _FakeClient:
    """httpx.AsyncClient 假体：post 非流式 / stream 流式"""
    def __init__(self, *a, **k):
        self.post_data = None

    async def aclose(self):
        pass

    def stream(self, method, url, json=None, headers=None):
        self.post_data = json
        return _FakeStreamCtx([
            'data: {"choices":[{"delta":{"content":"你好"}}]}',
            'data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":5,'
            '"prompt_cache_hit_tokens":2}}',
            "data: [DONE]",
        ])

    async def post(self, url, json=None, headers=None):
        self.post_data = json
        return _FakeResponse({
            "choices": [{"message": {"content": "你好"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                      "prompt_cache_hit_tokens": 2},
        })


@pytest.fixture()
def fake_upstream(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(llm_proxy.httpx, "AsyncClient", lambda *a, **k: fake)
    return fake


def test_llm_proxy_stream_forward_and_record(client, bound_device, fake_upstream, monkeypatch):
    recorded = {}
    monkeypatch.setattr("yuanai_core.usage.record_usage",
                        lambda uid, model, purpose, pt, ct, **kw: recorded.update(
                            {"uid": uid, "model": model, "purpose": purpose,
                             "pt": pt, "ct": ct, "kw": kw}))
    r = client.post("/api/v1/agent/llm/chat/completions",
                    json=_body(stream=True), headers=_h(bound_device))
    assert r.status_code == 200
    body_text = r.text
    assert "你好" in body_text and "[DONE]" in body_text
    # 强制 include_usage 已注入转发请求
    assert fake_upstream.post_data.get("stream_options") == {"include_usage": True}
    # 统一记账：usage_purpose=agent_llm，落绑定用户
    assert recorded["purpose"] == "agent_llm"
    assert recorded["pt"] == 10 and recorded["ct"] == 5
    assert recorded["kw"].get("cache_hit_tokens") == 2
    # 记账落绑定用户（agent_devices.user_id 映射）
    assert recorded["uid"] == bound_device["uid"]


def test_llm_proxy_nonstream_forward_and_record(client, bound_device, fake_upstream, monkeypatch):
    recorded = {}
    monkeypatch.setattr("yuanai_core.usage.record_usage",
                        lambda uid, model, purpose, pt, ct, **kw: recorded.update(
                            {"purpose": purpose, "pt": pt, "ct": ct}))
    r = client.post("/api/v1/agent/llm/chat/completions",
                    json=_body(stream=False), headers=_h(bound_device))
    assert r.status_code == 200
    assert r.json()["choices"][0]["message"]["content"] == "你好"
    assert recorded["purpose"] == "agent_llm"
    assert recorded["pt"] == 10 and recorded["ct"] == 5


# ---------------- Agent 端 lc 代理回退 ----------------

def test_lc_agent_proxy_endpoint(monkeypatch, tmp_path):
    import json as _json
    ident = {"agent_id": "12", "agent_secret": "SEC",
             "server_url": "ws://localhost:8000"}
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "agent_identity.json").write_text(_json.dumps(ident), encoding="utf-8")
    import utils.data_path
    monkeypatch.setattr(utils.data_path, "root_path", lambda: str(tmp_path))
    from yuanai_core.core.lc import _agent_proxy_endpoint
    ep = _agent_proxy_endpoint()
    assert ep == ("http://localhost:8000/api/v1/agent/llm", "SEC")


def test_lc_agent_proxy_none_without_identity(monkeypatch, tmp_path):
    import utils.data_path
    monkeypatch.setattr(utils.data_path, "root_path", lambda: str(tmp_path))
    from yuanai_core.core.lc import _agent_proxy_endpoint
    assert _agent_proxy_endpoint() is None


if __name__ == "__main__":
    print("测试入口：pytest test/test_llm_proxy.py -v")
