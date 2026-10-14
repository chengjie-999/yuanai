# -*- coding: utf-8 -*-
"""计划纯逻辑测试 — validate_steps/build_step_prompt/parse_step_output（零 DB 零 LLM）

含 P0 回归断言：ScriptRegistry.run 必须接受 progress_cb（2026-10-12 修复
委派路径 TypeError）。
运行：pytest test/test_plan_pure.py -v
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from yuanai_core.pure.plan import (  # noqa: E402
    validate_steps, validate_title_goal, build_step_prompt, parse_step_output,
)


# ---------------- validate_steps ----------------

def test_validate_ok():
    steps, err = validate_steps(json.dumps([
        {"skill": "collection", "desc": "抓取数据", "params": {"url": "https://x.com"}},
        {"skill": "analysis", "desc": "统计分析", "params": {"dataset_id": 1}},
    ]))
    assert not err and len(steps) == 2
    assert steps[0]["skill"] == "collection" and steps[1]["params"]["dataset_id"] == 1


def test_validate_skill_whitelist():
    steps, err = validate_steps([{"skill": "automation", "desc": "开浏览器"}])
    assert steps == [] and "skill" in err  # automation 挂账


def test_validate_step_count_limits():
    assert validate_steps([])[1]
    many = [{"skill": "analysis", "desc": f"步骤{i}"} for i in range(9)]
    assert "1-8" in validate_steps(many)[1]


def test_validate_desc_required_and_length():
    assert "desc" in validate_steps([{"skill": "analysis", "desc": ""}])[1]
    assert "300" in validate_steps([{"skill": "analysis", "desc": "长" * 301}])[1]


def test_validate_protocol_injection_blocked():
    """防脚本输出协议注入"""
    assert validate_steps([{"skill": "analysis", "desc": "__DASHBOARD__:/etc/x"}])[1]
    assert validate_steps([{"skill": "analysis", "desc": "ok",
                            "params": {"url": "__RESULT__:bad"}}])[1]


def test_validate_params_types():
    assert validate_steps([{"skill": "analysis", "desc": "ok",
                            "params": {"x": ["列表不合法"]}}])[1]
    assert validate_steps([{"skill": "analysis", "desc": "ok",
                            "params": {f"k{i}": i for i in range(9)}}])[1]


def test_validate_title_goal():
    assert validate_title_goal("", "x")[2]
    assert validate_title_goal("好", "y" * 501)[2]
    t, g, err = validate_title_goal("  分析报告  ", "目标")
    assert not err and t == "分析报告"


# ---------------- build_step_prompt ----------------

def test_step_prompt_self_contained():
    plan = {"title": "每日数据", "goal": "抓取并分析", "total_steps": 2}
    step = {"step_no": 2, "desc": "做统计", "params": {"dataset_id": 5}}
    prompt = build_step_prompt(plan, step, [{"step_no": 1, "desc": "抓取", "summary": "抓到100行"}])
    assert "【计划】每日数据" in prompt and "【总目标】" in prompt
    assert "当前步骤 2/2" in prompt and "dataset_id=5" in prompt
    assert "抓到100行" in prompt and "不要询问确认" in prompt


# ---------------- parse_step_output ----------------

def test_parse_dashboard_blocks(tmp_path):
    result_file = tmp_path / "result.json"
    result_file.write_text(json.dumps({"kpi": [{"label": "行数", "value": 100}]}),
                           encoding="utf-8")
    out = parse_step_output(f"分析完成\n__DASHBOARD__:{result_file}\n结论：正常")
    assert out["blocks"]["kpi"][0]["value"] == 100
    assert "__DASHBOARD__" not in out["text"] and "结论：正常" in out["text"]


def test_parse_strips_base64_and_markers():
    out = parse_step_output("结果\n__IMAGES__:data:image/png;base64,AAAA\n__HTML__URL:/api/x\n好了")
    assert "base64" not in out["text"] and "__HTML__URL" not in out["text"]
    assert "__IMAGES__" not in out["text"]
    assert "好了" in out["text"] and "结果" in out["text"]


def test_parse_truncation():
    out = parse_step_output("字" * 25000)
    assert out["truncated"] is True and len(out["text"]) == 20000


# ---------------- P0 回归：registry.run 接受 progress_cb ----------------

def test_registry_run_accepts_progress_cb():
    from agent.scripts.registry import ScriptRegistry
    r = ScriptRegistry("agent/datanalysis/scripts")
    out = r.run("不存在的脚本", None, progress_cb=lambda c, t, m: None)
    assert "未知脚本" in out  # 不抛 TypeError 即修复生效


if __name__ == "__main__":
    print("测试入口：pytest test/test_plan_pure.py -v")


# ---------------- script 字段校验（融合 R4） ----------------

def test_validate_script_field_matrix():
    base = {"skill": "analysis", "desc": "做统计"}
    ok, err = validate_steps(json.dumps([{**base, "script": "descriptive_stats"}]))
    assert not err and ok[0]["script"] == "descriptive_stats"
    ok2, _ = validate_steps(json.dumps([{**base, "script": "描述性统计分析"}]))
    assert ok2[0]["script"] == "描述性统计分析"
    # 缺省空串放行
    ok3, _ = validate_steps(json.dumps([base]))
    assert ok3[0]["script"] == ""
    # 超长 / 路径语义 / 协议标记 拒绝
    assert validate_steps(json.dumps([{**base, "script": "x" * 65}]))[1]
    assert validate_steps(json.dumps([{**base, "script": "../evil"}]))[1]
    assert validate_steps(json.dumps([{**base, "script": "__DASHBOARD__:x"}]))[1]
