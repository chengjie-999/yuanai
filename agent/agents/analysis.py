"""数据分析 Agent：LLM 意图匹配 → 派发分析脚本。
配置从 skills/analysis/skill.yaml 加载，提示词和脚本列表无需改代码即可更新。"""

from agent.agents.base import ScriptDispatchAgent
from skills import skill_registry


class AnalysisAgent(ScriptDispatchAgent):
    def __init__(self):
        super().__init__(skill_registry.get("analysis"))

    def _dispatch_builtin(self, name: str, params: dict) -> str:
        from yuanai_core.tools.data_tools import list_datasets, preview_dataset, analyze_dataset, transform_dataset

        handlers = {
            "builtin_list_datasets": lambda: list_datasets.invoke({}),
            "builtin_preview_dataset": lambda: preview_dataset.invoke(
                {"dataset_id": params.get("dataset_id", 0)}
            ),
            "builtin_analyze_dataset": lambda: analyze_dataset.invoke(
                {"dataset_id": params.get("dataset_id", 0)}
            ),
            "builtin_transform_dataset": lambda: transform_dataset.invoke({
                "dataset_id": params.get("dataset_id", 0),
                "operation": params.get("operation", ""),
                "params": params.get("params", "{}"),
            }),
        }
        handler = handlers.get(name)
        return handler() if handler else f"未知内置操作: {name}"
