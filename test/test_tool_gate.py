"""V1-2 审批分层测试（2026-11-05）

覆盖：gate 分级（L0/L1 直执行、L2 审批、未登记默认 L3 fail-closed）；
LangGraph 路径 gated 包装（无法交互审批 → L2/L3 拒绝执行）；
云端决议注册表（配对/未知/超时）；/chat/stream 决议早分支。
"""
import asyncio

import pytest
from langchain_core.tools import tool as lang_tool

from yuanai_core.pure.tool_gate import gate, LEVEL_L0, LEVEL_L1, LEVEL_L2, LEVEL_L3


# ---------------- gate 分级 ----------------

def test_gate_l0_readonly_allow():
    for name in ("get_user_memory", "read_data_file", "search_web", "list_datasets",
                 "get_current_time", "retrieve_knowledge", "preview_dataset"):
        v = gate(name)
        assert v["level"] == LEVEL_L0 and not v["ask"] and not v["block"], name


def test_gate_l1_reversible_write_allow():
    for name in ("save_data_csv", "remember_user_info", "create_plan", "set_theme"):
        v = gate(name)
        assert v["level"] == LEVEL_L1 and not v["ask"] and not v["block"], name


def test_gate_l2_needs_approval():
    for name in ("execute_plan", "organize_user_memory"):
        v = gate(name)
        assert v["level"] == LEVEL_L2 and v["ask"] and not v["block"], name


def test_gate_undeclared_defaults_l3():
    """未登记工具默认 L3 拦截（fail-closed）——新工具必须登记否则云端不可用"""
    v = gate("delete_memory")
    assert v["level"] == LEVEL_L3 and v["block"] and not v["ask"]
    v = gate("__unknown_tool__")
    assert v["level"] == LEVEL_L3 and v["block"]


def test_gate_declared_tools_cover_all_shared():
    """共享工具全部登记（守门员：漏登记 = 云端直连被 L3 拦截）"""
    from yuanai_core.tools import all_tools
    for t in all_tools:
        assert gate(t.name)["level"] != LEVEL_L3, f"工具 {t.name} 未登记（默认 L3 会被拦截）"


# ---------------- LangGraph 路径 gated 包装（fail-closed） ----------------

def test_gated_tools_l0_l1_passthrough():
    from yuanai_core.core.chat import _gated_tools

    @lang_tool
    def add_one(x: int) -> int:
        """加一"""
        return x + 1

    def _allow(name, args):
        return {"level": LEVEL_L0, "ask": False, "block": False, "reason": ""}

    wrapped = _gated_tools([add_one], _allow)
    assert wrapped[0].invoke({"x": 1}) == 2  # L0 直执行原样透传
    assert wrapped[0].name == "add_one"


def test_gated_tools_l2_l3_rejected_without_approval_channel():
    from yuanai_core.core.chat import _gated_tools

    calls = {"n": 0}

    @lang_tool
    def fake_tool(x: int) -> str:
        """测试工具"""
        calls["n"] += 1
        return "executed"

    # 自定义 gate：全部 L2 → 拒绝且不执行
    def _g(name, args):
        return {"level": LEVEL_L2, "ask": True, "block": False, "reason": "x"}

    wrapped = _gated_tools([fake_tool], _g)
    out = wrapped[0].invoke({"x": 1})
    assert "拒绝执行" in out
    assert calls["n"] == 0

    def _g3(name, args):
        return {"level": LEVEL_L3, "ask": False, "block": True, "reason": "y"}

    wrapped3 = _gated_tools([fake_tool], _g3)
    assert "已拦截" in wrapped3[0].invoke({"x": 1})
    assert calls["n"] == 0


# ---------------- 云端决议注册表 ----------------

def test_approvals_roundtrip_approve():
    from api.v1.chat import approvals

    async def _run():
        async def wait():
            return await approvals.await_decision("d1", timeout=5)

        t = asyncio.create_task(wait())
        await asyncio.sleep(0.05)
        assert approvals.pending_count() == 1
        assert approvals.resolve_decision("d1", True) is True
        assert await t == "approve"
        assert approvals.pending_count() == 0

    asyncio.run(_run())


def test_approvals_roundtrip_deny_and_unknown():
    from api.v1.chat import approvals

    async def _run():
        async def wait():
            return await approvals.await_decision("d2", timeout=5)

        t = asyncio.create_task(wait())
        await asyncio.sleep(0.05)
        assert approvals.resolve_decision("d2", False) is True
        assert await t == "deny"
        # 未知/已决 id → False
        assert approvals.resolve_decision("d2", True) is False
        assert approvals.resolve_decision("nope", True) is False

    asyncio.run(_run())


def test_approvals_timeout_returns_none():
    from api.v1.chat import approvals

    async def _run():
        out = await approvals.await_decision("d3", timeout=0.1)
        assert out is None
        assert approvals.pending_count() == 0

    asyncio.run(_run())


# ---------------- /chat/stream 决议早分支 ----------------

def test_stream_decision_branch_resolves_without_pending(client, auth_headers):
    """决议请求早返回（不烧配额/不走 LLM）；无挂起审批 → decision_resolved=false。
    配对成功的闭环由 test_approvals_roundtrip_* 在单 loop 内覆盖（TestClient
    应用跑在独立线程 loop，跨 loop 置 Future 非线程安全，不在此测）。"""
    resp = client.post("/api/v1/chat/stream",
                       json={"decision": {"decision_id": "no_such_id", "approve": True},
                             "model": "deepseek-flash", "prompt": "", "history": [],
                             "system_prompt": "x", "session_id": "s_gate"},
                       headers=auth_headers)
    assert resp.status_code == 200
    body = resp.text
    assert "decision_resolved" in body


if __name__ == "__main__":
    print("测试入口：pytest test/test_tool_gate.py -v")
