"""上下文用量端点 + token 估算纯函数 + usage_event 数据源（2026-11-06）

功能：消息脚注「本次消耗」（/stream usage_event）与顶栏「上下文用量」
徽标（/chat/context-usage，Claude Code /context 风格）的后端支撑。"""

import pytest


# ---------- 纯函数：token 估算 ----------

def test_estimate_tokens():
    from yuanai_core.pure.token_estimate import estimate_tokens
    assert estimate_tokens("") == 0
    assert estimate_tokens("你好世界") == 4           # CJK 每字 1 token
    assert estimate_tokens("hello world test") == 4   # 15 字符 ≈ 4 token
    assert estimate_tokens("你好 abcdefgh") == 5      # 2 中文 + (空格+8 ascii)/4 ≈ 5


def test_model_context_window():
    from yuanai_core.pure.token_estimate import model_context_window
    assert model_context_window("deepseek-flash") == 128_000
    assert model_context_window("doubao-seed-2-0-lite-260915") == 256_000
    assert model_context_window("unknown-model") == 128_000  # 未登记兜底


# ---------- usage_from_llm（/stream usage_event 数据源） ----------

class _FakeResponse:
    def __init__(self, usage_metadata):
        self.usage_metadata = usage_metadata


def test_usage_from_llm_accumulates():
    from yuanai_core.usage import UsageTrackingHandler, usage_from_llm

    class _LLM:
        pass

    llm = _LLM()
    h = UsageTrackingHandler(default_model="deepseek-flash")
    llm.callbacks = [h]
    # 同一请求多轮 LLM 调用（工具循环）→ 累加为单请求总量
    h.on_llm_end(_FakeResponse({"input_tokens": 100, "output_tokens": 50}),
                 invocation_params={})
    h.on_llm_end(_FakeResponse({"input_tokens": 20, "output_tokens": 5,
                                "prompt_cache_hit_tokens": 15}),
                 invocation_params={})
    u = usage_from_llm(llm)
    assert u["input_tokens"] == 120
    assert u["output_tokens"] == 55
    assert u["cache_hit_tokens"] == 15
    assert u["model"] == "deepseek-flash"


def test_accumulate_llm_usage_deepseek_path():
    """DeepSeek 原生通道绕过 langchain 回调——显式累计同样落到 handler"""
    from yuanai_core.usage import UsageTrackingHandler, usage_from_llm, accumulate_llm_usage

    class _LLM:
        pass

    llm = _LLM()
    llm.callbacks = [UsageTrackingHandler(default_model="deepseek-flash")]
    accumulate_llm_usage(llm, "deepseek-flash", 300, 80, cache_hit_tokens=120)
    accumulate_llm_usage(llm, "deepseek-flash", 10, 5)
    u = usage_from_llm(llm)
    assert u["input_tokens"] == 310
    assert u["output_tokens"] == 85
    assert u["cache_hit_tokens"] == 120


def test_accumulate_llm_usage_no_handler():
    """无 handler 挂载（本地 Agent 等）静默跳过"""
    from yuanai_core.usage import accumulate_llm_usage

    class _LLM:
        callbacks = []

    accumulate_llm_usage(_LLM(), "deepseek-flash", 1, 1)  # 不抛


def test_usage_from_llm_empty():
    from yuanai_core.usage import usage_from_llm

    class _LLM:
        pass

    llm = _LLM()
    llm.callbacks = []
    assert usage_from_llm(llm) == {}


def test_usage_event_skips_without_usage():
    """桥接路径无云端 LLM 实例 → usage_event 不发（返回空 dict）"""
    from api.v1.chat.router import _usage_event

    class _LLM:
        pass

    llm = _LLM()
    llm.callbacks = []
    assert _usage_event(llm, "deepseek-flash") == {}


# ---------- 端点 ----------

def _login(client, username, password="test1234"):
    r = client.post("/api/v1/auth/login",
                    json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _uid(db, username):
    """注册（幂等：已存在则查回）返回用户 id——测试可重复跑"""
    r = db.register_user(username, "test1234")
    if "error" not in r:
        return r["id"]
    from db.session import User
    with db.session() as sess:
        return sess.query(User).filter_by(username=username).first().id


def test_context_usage_requires_login(client):
    assert client.get("/api/v1/chat/context-usage",
                      params={"sid": "nope"}).status_code == 401


def test_context_usage_flow(client):
    from db.session import get_db, AIChat
    db = get_db()
    uid = _uid(db, "__ctx_user__")
    headers = _login(client, "__ctx_user__")
    main = db.ensure_main_session(uid)
    sid = main["session_id"]
    # 直接落库几条消息（省去 /chat/save 链路）
    with db.session() as sess:
        for i in range(3):
            sess.add(AIChat(session_id=sid,
                            role="user" if i % 2 == 0 else "assistant",
                            content="你好世界" * (10 * (i + 1))))
        sess.commit()
    resp = client.get("/api/v1/chat/context-usage",
                      params={"sid": sid}, headers=headers)
    assert resp.status_code == 200
    d = resp.json()
    assert d["limit"] == 128_000
    assert d["history_capped"] == 60            # 主对话 60 条截断口径
    assert d["truncated"] is False
    assert 0 < d["used"] < d["limit"]
    assert 0 <= d["percent"] <= 100
    # 会话不存在 → 404
    assert client.get("/api/v1/chat/context-usage",
                      params={"sid": "no-such-sid"},
                      headers=headers).status_code == 404


def test_context_usage_ownership(client):
    from db.session import get_db
    db = get_db()
    uid_a = _uid(db, "__ctx_a__")
    _uid(db, "__ctx_b__")
    sid = db.ensure_main_session(uid_a)["session_id"]
    headers2 = _login(client, "__ctx_b__")
    assert client.get("/api/v1/chat/context-usage",
                      params={"sid": sid},
                      headers=headers2).status_code == 403
