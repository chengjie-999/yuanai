# -*- coding: utf-8 -*-
"""计划执行器测试 — mock HTTP + 假 registry 驱动真实 run_once（零网络零 MySQL）

融合后（R4）：步骤绑定脚本 → registry.run 零 LLM 直跑；未绑定 → bind_tools
兜底（本测试 mock 掉 _run_fallback_llm 避免真实 LLM）。
运行：pytest test/test_plan_executor.py -v
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from agent.plan_executor import PlanExecutor  # noqa: E402


class FakeRegistry:
    """假 ScriptRegistry：resolve + run 可编程"""

    def __init__(self, output="结果文本", exc=None):
        self._output = output
        self._exc = exc
        self.calls = []

    def resolve(self, name):
        return name if name == "描述性统计分析" else None

    def run(self, name, params=None, progress_cb=None):
        self.calls.append((name, dict(params or {}), progress_cb))
        if self._exc:
            raise self._exc
        if progress_cb:
            progress_cb(1, 2, "半程")
        return self._output


def _mk_executor(monkeypatch, registry=None, enabled_skills=None):
    ex = PlanExecutor("1", "secret", "http://localhost:8000",
                      enabled_skills=enabled_skills)
    if registry is not None:
        monkeypatch.setattr(ex, "_get_registry", lambda skill: registry)
    return ex


def _mk_http(monkeypatch, ex, responses, calls):
    """responses: path -> 响应 dict；step-done/step-failed 记录进 calls"""
    def fake_http(path, payload=None, timeout=60):
        if path.startswith("/step-done") or path.startswith("/step-failed"):
            calls.append((path, payload))
        if path in responses:
            return responses[path]
        return {"ok": True}
    monkeypatch.setattr(ex, "_http", fake_http)


_PLAN = {"id": 1, "title": "测试", "goal": "抓取并分析", "total_steps": 1,
         "status": "running"}
_STEP = {"id": 11, "plan_id": 1, "step_no": 1, "skill": "analysis",
         "script": "描述性统计分析",
         "desc": "做统计分析", "params_json": json.dumps({"dataset_id": 5})}


def test_pull_empty_idle(monkeypatch):
    ex = _mk_executor(monkeypatch)
    monkeypatch.setattr(ex, "_http", lambda path, payload=None, timeout=60: {"empty": True})
    assert ex.run_once() == {"idle": True}


def test_bound_script_runs_zero_llm(monkeypatch):
    """步骤绑定脚本 → registry.run 直跑（不经过 LLM），params_json 正确解析"""
    reg = FakeRegistry(output="分析完成")
    ex = _mk_executor(monkeypatch, registry=reg)
    calls = []
    _mk_http(monkeypatch, ex, {"/pull": {"plan": _PLAN, "step": _STEP, "prev": []}}, calls)
    # 确保没有走到兜底 LLM 路径
    monkeypatch.setattr(ex, "_run_fallback_llm",
                        lambda *a, **k: ("failed_noretry", "不应走到兜底"))
    r = ex.run_once()
    assert r["executed"] == 1 and r["reported"] is True
    name, params, cb = reg.calls[0]
    assert name == "描述性统计分析" and params == {"dataset_id": 5} and cb is not None
    path, payload = calls[0]
    assert path == "/step-done" and payload["script"] == "描述性统计分析"
    assert payload["result_json"]["text"] == "分析完成"


def test_bound_script_missing_falls_back(monkeypatch):
    """绑定脚本本机不存在 → 自动降级现场选（标 fallback 语义，走兜底路径）"""
    reg = FakeRegistry(output="兜底结果")
    reg.resolve = lambda name: None  # 本机无此脚本
    ex = _mk_executor(monkeypatch, registry=reg)
    calls = []
    _mk_http(monkeypatch, ex, {"/pull": {"plan": _PLAN, "step": _STEP, "prev": []}}, calls)
    monkeypatch.setattr(ex, "_run_fallback_llm",
                        lambda skill, plan, step, prev, cb: ("done_script", "兜底结果"))
    r = ex.run_once()
    assert r["executed"] == 1
    assert calls[0][1]["script"] == "描述性统计分析"  # bound 名回传（实际脚本由兜底选）


def test_unbound_script_fallback_path(monkeypatch):
    """无绑定脚本（云端 fallback 建的步骤）→ _run_fallback_llm"""
    step = {k: v for k, v in _STEP.items() if k != "script"}
    reg = FakeRegistry(output="现场选的结果")
    ex = _mk_executor(monkeypatch, registry=reg)
    calls = []
    _mk_http(monkeypatch, ex, {"/pull": {"plan": _PLAN, "step": step, "prev": []}}, calls)
    monkeypatch.setattr(ex, "_run_fallback_llm",
                        lambda skill, plan, s, prev, cb: ("done_script", "现场选的结果"))
    r = ex.run_once()
    assert r["executed"] == 1 and calls[0][1]["script"] == ""


def test_skill_whitelist_blocked(monkeypatch):
    step = {**_STEP, "skill": "automation"}
    ex = _mk_executor(monkeypatch)
    calls = []
    _mk_http(monkeypatch, ex, {"/pull": {"plan": _PLAN, "step": step, "prev": []}}, calls)
    r = ex.run_once()
    assert r["executed"] == 0 and r["retryable"] is False
    assert "白名单" in calls[0][1]["error"]


def test_tray_toggle_disabled(monkeypatch):
    ex = _mk_executor(monkeypatch, enabled_skills=["collection"])
    calls = []
    _mk_http(monkeypatch, ex, {"/pull": {"plan": _PLAN, "step": _STEP, "prev": []}}, calls)
    r = ex.run_once()
    assert r["retryable"] is False and "关闭" in calls[0][1]["error"]


def test_tray_toggle_callable_live(monkeypatch):
    reg = FakeRegistry(output="ok")
    ex = _mk_executor(monkeypatch, registry=reg, enabled_skills=lambda: ["analysis"])
    calls = []
    _mk_http(monkeypatch, ex, {"/pull": {"plan": _PLAN, "step": _STEP, "prev": []}}, calls)
    assert ex.run_once()["executed"] == 1  # 实时读取开关，通过


def test_exception_retryable(monkeypatch):
    reg = FakeRegistry(exc=TimeoutError("网络超时"))
    ex = _mk_executor(monkeypatch, registry=reg)
    calls = []
    _mk_http(monkeypatch, ex, {"/pull": {"plan": _PLAN, "step": _STEP, "prev": []}}, calls)
    r = ex.run_once()
    assert r["retryable"] is True and "执行异常" in calls[0][1]["error"]


def test_deterministic_failure_no_retry(monkeypatch):
    reg = FakeRegistry(output="无法处理：缺少 URL，请先提供网址")
    ex = _mk_executor(monkeypatch, registry=reg)
    calls = []
    _mk_http(monkeypatch, ex, {"/pull": {"plan": _PLAN, "step": _STEP, "prev": []}}, calls)
    r = ex.run_once()
    assert r["retryable"] is False and "无法处理" in calls[0][1]["error"]


def test_report_retry_then_reported_false(monkeypatch):
    """上报失败 3 次重试后 reported=False（看门狗兜底）"""
    reg = FakeRegistry(output="正常结果")
    ex = _mk_executor(monkeypatch, registry=reg)

    def failing_http(path, payload=None, timeout=60):
        if path == "/pull":
            return {"plan": _PLAN, "step": _STEP, "prev": []}
        raise OSError("网络断了")

    monkeypatch.setattr(ex, "_http", failing_http)
    from agent import plan_executor as pe
    monkeypatch.setattr(pe, "REPORT_RETRY_DELAY_S", 0)
    r = ex.run_once()
    assert r["reported"] is False


if __name__ == "__main__":
    print("测试入口：pytest test/test_plan_executor.py -v")
