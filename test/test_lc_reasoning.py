# -*- coding: utf-8 -*-
"""lc.py 推理强度解析测试 — 显式参数 > contextvar > env；前缀匹配覆盖新版本模型

纯离线（monkeypatch ChatOpenAI 捕获构造参数）。运行：pytest test/test_lc_reasoning.py -v
"""
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')


@pytest.fixture()
def lc_mod(monkeypatch):
    import yuanai_core.core.lc as lc
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.clear()
            captured.update(kwargs)

    monkeypatch.setattr(lc, "ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr(lc, "_get_stored_key", lambda p: "sk-test")
    monkeypatch.setattr(lc, "get_api_key", lambda t: "sk-test")
    return lc, captured


def test_explicit_param_wins(lc_mod):
    lc, captured = lc_mod
    lc.get_llm("deepseek-v4-pro", reasoning_effort="high")
    assert captured["extra_body"] == {"reasoning_effort": "high"}

    lc.get_llm("deepseek-v4-pro", reasoning_effort="medium")
    assert captured["extra_body"] == {"reasoning_effort": "medium"}

    lc.get_llm("deepseek-v4-pro", reasoning_effort="low")
    assert captured["extra_body"] == {"reasoning_effort": "low"}


def test_contextvar_second(lc_mod, monkeypatch):
    lc, captured = lc_mod
    tok = lc.current_reasoning_effort.set("high")
    try:
        lc.get_llm("deepseek-v4-pro")
        assert captured["extra_body"] == {"reasoning_effort": "high"}
        # 新版本模型（如 deepseek-4.1）/ reasoner 在 models.json 注册后 →
        # 前缀匹配自动带推理参数（测试里模拟注册：加入 dsllm 列表）
        monkeypatch.setattr(lc, "dsllm", lc.dsllm + ["deepseek-4.1", "deepseek-reasoner"])
        lc.get_llm("deepseek-4.1")
        assert captured["extra_body"] == {"reasoning_effort": "high"}
        # reasoner 恒 high
        lc.get_llm("deepseek-reasoner")
        assert captured["extra_body"] == {"reasoning_effort": "high"}
    finally:
        lc.current_reasoning_effort.reset(tok)


def test_env_fallback(lc_mod, monkeypatch):
    lc, captured = lc_mod
    monkeypatch.setattr(lc, "REASONING_EFFORT", "low")
    lc.get_llm("deepseek-v4-flash")
    assert captured["extra_body"] == {"reasoning_effort": "low"}


def test_reasoning_false_no_extra_body(lc_mod):
    lc, captured = lc_mod
    lc.get_llm("deepseek-v4-pro", reasoning=False)
    assert "extra_body" not in captured


def test_doubao_no_reasoning_param(lc_mod):
    """豆包分支不带 reasoning_effort（思考由方舟接入点控制）"""
    lc, captured = lc_mod
    lc.get_llm("doubao-seed-2-0-pro-260215", reasoning_effort="high")
    assert "extra_body" not in captured


def test_chat_request_schema_has_effort():
    """WS 协议 ChatRequest 带 reasoning_effort（默认 low）"""
    from yuanai_core.core.schemas import ChatRequest
    req = ChatRequest(user_id=1)
    assert req.reasoning_effort == "low"
    req2 = ChatRequest(user_id=1, reasoning_effort="high")
    assert req2.reasoning_effort == "high"


if __name__ == "__main__":
    print("测试入口：pytest test/test_lc_reasoning.py -v")


def test_get_llm_short_name_alias(monkeypatch):
    """回归：skills/*.yaml 短名（doubao-seed-2-1-lite）曾落 custom 分支报「未找到 API Key」，
    委派/@定向/计划执行器共用 get_llm 工厂——前缀匹配到已注册完整 ID 后替换。"""
    import os
    monkeypatch.setenv("DOUBAO_API_KEY", "test-key")
    from yuanai_core.core.lc import get_llm
    llm = get_llm("doubao-seed-2-1-lite", reasoning=False)
    assert llm.model_name == "doubao-seed-2-1-lite-260915"
    llm2 = get_llm("doubao-seed-2-1-pro", reasoning=False)
    assert llm2.model_name == "doubao-seed-2-1-pro-260628"
    # 完整 ID 原样通过
    llm3 = get_llm("doubao-seed-2-1-lite-260915", reasoning=False)
    assert llm3.model_name == "doubao-seed-2-1-lite-260915"


def test_get_llm_retired_id_routes_to_new(monkeypatch):
    """已退役 ID（存量配置）静默路由到新 ID（升级知识表）"""
    monkeypatch.setenv("DOUBAO_API_KEY", "test-key")
    from yuanai_core.core.lc import get_llm
    llm = get_llm("doubao-seed-2-0-lite-260215", reasoning=False)
    assert llm.model_name == "doubao-seed-2-1-lite-260915"
    llm2 = get_llm("deepseek-v4-flash", reasoning=False)
    assert llm2.model_name == "deepseek-flash"
