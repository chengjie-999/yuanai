"""数据分析 Agent：LLM 意图匹配 → 派发分析脚本"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from yuanai_core.core.lc import get_llm
from agent.scripts.registry import ScriptRegistry

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是数据分析专家。根据用户需求，从可用脚本列表中选择最合适的，提取参数。

返回 JSON 格式（只返回 JSON，不要其他文字）：
{"script": "脚本名", "params": {"参数名": "值"}}
如果无法匹配任何脚本，返回：
{"script": null, "reason": "原因"}
如果要用 list_datasets / preview_dataset 等基础操作，使用脚本名 "builtin_list_datasets" 或 "builtin_preview_dataset"。
如果用户提到了具体的文件名但没有提供 dataset_id，先用 "builtin_list_datasets" 查找。"""


class AnalysisAgent:
    def __init__(self):
        self.registry = ScriptRegistry("agent.datanalysis.scripts")

    def run(self, prompt: str) -> str:
        script_list = self.registry.list_for_llm()

        # 补充内置基础操作
        builtin = (
            "- builtin_list_datasets: 列出所有可用数据集\n"
            "- builtin_preview_dataset: 预览数据集前N行，参数 dataset_id\n"
            "- builtin_analyze_dataset: 对数据集执行完整统计分析，参数 dataset_id"
        )
        full_list = f"{builtin}\n{script_list}" if "暂无可用脚本" not in script_list else builtin

        llm = get_llm("doubao-seed-2-0-pro-260215", temperature=0, verbose=False)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"可用脚本：\n{full_list}\n\n用户需求：{prompt}"),
        ]
        response = llm.invoke(messages)

        try:
            text = response.content.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            choice = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("LLM 返回非 JSON: %s", response.content[:200])
            return f"无法解析意图，请重新描述需求。原始响应: {response.content[:300]}"

        if not choice.get("script"):
            return f"无法处理：{choice.get('reason', '未知原因')}"

        script_name = choice["script"]
        params = choice.get("params", {})

        # 内置基础操作
        if script_name.startswith("builtin_"):
            return self._run_builtin(script_name, params)

        return self.registry.run(script_name, **params)

    def _run_builtin(self, name: str, params: dict) -> str:
        from yuanai_core.tools.data_tools import list_datasets, preview_dataset, analyze_dataset

        if name == "builtin_list_datasets":
            return list_datasets.invoke({})
        elif name == "builtin_preview_dataset":
            dataset_id = params.get("dataset_id", 0)
            return preview_dataset.invoke({"dataset_id": dataset_id})
        elif name == "builtin_analyze_dataset":
            dataset_id = params.get("dataset_id", 0)
            return analyze_dataset.invoke({"dataset_id": dataset_id})
        return f"未知内置操作: {name}"
