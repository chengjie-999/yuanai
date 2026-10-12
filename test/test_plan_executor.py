# -*- coding: utf-8 -*-
"""计划执行器测试 — mock HTTP + mock agent 驱动真实 run_once（零网络零 MySQL）

运行：pytest test/test_plan_executor.py -v
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from agent.plan_executor import PlanExecutor  # noqa: E402


class FakeAgent:
    """假 ScriptDispatchAgent：可编程返回与 last_dispatch"""

    def __init__(self, output="结果文本", exc=None, script="测试脚本"):
        self._output = output
        self._exc = exc
        self.last_dispatch = {"script": script, "params": {}}
        self.prompts = []

    def run(self, prompt, progress_cb=None):
        self.prompts.append(prompt)
        if self._exc:
            raise self._exc
        if progress_cb:
            progress_cb(1, 2, "半程")
        return self._output


def _mk_executor(monkeypatch, agent=None, enabled_skills=None):
    ex = PlanExecutor("1", "secret", "http://localhost:8000",
                      enabled_skills=enabled_skills)
    if agent is not None:
        monkeypatch.setattr(ex, "_get_agent", lambda skill: agent)
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
         "desc": "做统计分析", "params": {"dataset_id": 5}}


def test_pull_empty_idle(monkeypatch):
    ex = _mk_executor(monkeypatch)
    monkeypatch.setattr(ex, "_http", lambda path, payload=None, timeout=60: {"empty": True})
    assert ex.run_once() == {"idle": True}


def test_step_done_with_dashboard_blocks(monkeypatch, tmp_path):
    """正常执行：__DASHBOARD__ 解析成 blocks，step-done payload 正确"""
    result_file = tmp_path / "r.json"
    result_file.write_text(json.dumps({"kpi": [{"label": "行数", "value": 100}]}),
                           encoding="utf-8")
    agent = FakeAgent(output=f"分析完成\n__DASHBOARD__:{result_file}\n结论")
    ex = _mk_executor(monkeypatch, agent=agent)
    calls = []
    _mk_http(monkeypatch, ex, {"/pull": {"plan": _PLAN, "step": _STEP, "prev": []}}, calls)
    r = ex.run_once()
    assert r["executed"] == 1 and r["reported"] is True
    path, payload = calls[0]
    assert path == "/step-done" and payload["script"] == "测试脚本"
    assert payload["result_json"]["blocks"]["kpi"][0]["value"] == 100
    assert "分析完成" in payload["summary"]
    # prompt 自包含
    assert "dataset_id=5" in agent.prompts[0] and "不要询问确认" in agent.prompts[0]


def test_skill_whitelist_blocked(monkeypatch):
    step = {**_STEP, "skill": "automation"}
    ex = _mk_executor(monkeypatch)
    calls = []
    _mk_http(monkeypatch, ex, {"/pull": {"plan": _PLAN, "step": step, "prev": []}}, calls)
    r = ex.run_once()
    assert r["executed"] == 0 and r["retryable"] is False
    assert "白名单" in calls[0][1]["error"]


def test_tray_toggle_disabled(monkeypatch):
    """托盘开关关闭该技能 → 确定性失败不重试"""
    ex = _mk_executor(monkeypatch, enabled_skills=["collection"])
    calls = []
    _mk_http(monkeypatch, ex, {"/pull": {"plan": _PLAN, "step": _STEP, "prev": []}}, calls)
    r = ex.run_once()
    assert r["retryable"] is False and "关闭" in calls[0][1]["error"]


def test_tray_toggle_callable_live(monkeypatch):
    ex = _mk_executor(monkeypatch, agent=FakeAgent(),
                      enabled_skills=lambda: ["analysis"])
    calls = []
    _mk_http(monkeypatch, ex, {"/pull": {"plan": _PLAN, "step": _STEP, "prev": []}}, calls)
    assert ex.run_once()["executed"] == 1  # 实时读取开关，通过


def test_exception_retryable(monkeypatch):
    agent = FakeAgent(exc=TimeoutError("网络超时"))
    ex = _mk_executor(monkeypatch, agent=agent)
    calls = []
    _mk_http(monkeypatch, ex, {"/pull": {"plan": _PLAN, "step": _STEP, "prev": []}}, calls)
    r = ex.run_once()
    assert r["retryable"] is True and "执行异常" in calls[0][1]["error"]


def test_deterministic_failure_no_retry(monkeypatch):
    agent = FakeAgent(output="无法处理：缺少 URL，请先提供网址")
    ex = _mk_executor(monkeypatch, agent=agent)
    calls = []
    _mk_http(monkeypatch, ex, {"/pull": {"plan": _PLAN, "step": _STEP, "prev": []}}, calls)
    r = ex.run_once()
    assert r["retryable"] is False and "无法处理" in calls[0][1]["error"]


def test_report_retry_then_reported_false(monkeypatch):
    """上报失败 3 次重试后 reported=False（看门狗兜底）"""
    agent = FakeAgent(output="正常结果")
    ex = _mk_executor(monkeypatch, agent=agent)

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
