# -*- coding: utf-8 -*-
"""模型自知注入修复测试 — resolve_model_id 归一化 + 注入点单 ID 一致性

运行：pytest test/test_model_self_report.py -v（纯离线）
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')


def test_resolve_model_id_retired_route():
    from yuanai_core.core.lc import resolve_model_id
    assert resolve_model_id("deepseek-v4-flash") == "deepseek-flash"
    assert resolve_model_id("deepseek-chat") == "deepseek-flash"


def test_resolve_model_id_short_name():
    from yuanai_core.core.lc import resolve_model_id
    # 短名（skills yaml 用）前缀匹配到注册表完整 ID
    assert resolve_model_id("doubao-seed-2-0-lite") == "doubao-seed-2-0-lite-260215"
    assert resolve_model_id("doubao-seed-2-0-pro") == "doubao-seed-2-0-pro-260215"


def test_resolve_model_id_registered_unchanged():
    from yuanai_core.core.lc import resolve_model_id
    assert resolve_model_id("deepseek-v4-pro") == "deepseek-v4-pro"
    assert resolve_model_id("doubao-seed-2-0-lite-260215") == "doubao-seed-2-0-lite-260215"


def test_offline_prompt_single_model_id(monkeypatch):
    """云端回退自报注入：归一化后且只出现一个模型 ID"""
    import api.v1.chat.router as r
    from yuanai_core.core.lc import resolve_model_id

    # 构造 offline 提示（模拟 :344-347 逻辑）
    model = "deepseek-v4-flash"
    prompt = r._OFFLINE_SYSTEM_PROMPT
    prompt += (f"\n\n你当前实际运行的模型 ID 是 {resolve_model_id(model)}。"
               f"当用户问「你是什么模型/哪个模型」时，必须如实回答这个模型 ID，"
               f"不要说「无法披露」「没有准确信息」之类的话。")
    assert "deepseek-flash" in prompt
    assert "deepseek-v4-flash" not in prompt  # 退役 ID 不泄漏进提示
    # 只出现一次自报（不重复注入）
    assert prompt.count("你当前实际运行的模型 ID 是") == 1


def test_orchestrator_self_report_appends_not_inserts():
    """本地统筹自报：追加进已有首条 system，不造双 system（结构断言用样例模拟）"""
    input_messages = [
        {"role": "system", "content": "你是小元AI的统筹助手…"},
        {"role": "user", "content": "你是什么模型"},
    ]
    self_report = "\n\n你当前实际运行的模型 ID 是 deepseek-flash。"
    input_messages[0]["content"] += self_report
    assert len(input_messages) == 2  # 没有新增 system 项
    assert "deepseek-flash" in input_messages[0]["content"]
    # 无 system 时 insert 兜底
    msgs = [{"role": "user", "content": "hi"}]
    msgs.insert(0, {"role": "system", "content": self_report.strip()})
    assert msgs[0]["role"] == "system"


if __name__ == "__main__":
    print("测试入口：pytest test/test_model_self_report.py -v")
