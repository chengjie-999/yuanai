"""数据分析 Agent：LLM 意图匹配 → 派发分析脚本"""
from agent.agents.base import ScriptDispatchAgent


class AnalysisAgent(ScriptDispatchAgent):
    script_dir = "agent/datanalysis/scripts"
    model_name = "doubao-seed-2-0-pro-260215"

    system_prompt = """你是数据分析专家。根据用户需求，从可用操作中选择最合适的，提取参数。

返回 JSON 格式（只返回 JSON，不要其他文字）：
{"script": "脚本名", "params": {"参数名": "值"}}
如果无法匹配任何操作，返回：
{"script": null, "reason": "原因"}
如果用户提到了具体的文件名但没有提供 dataset_id，先用 "builtin_list_datasets" 查找。"""

    builtins = {
        "builtin_list_datasets": "列出所有可用数据集",
        "builtin_preview_dataset": "预览数据集前N行，参数 dataset_id",
        "builtin_analyze_dataset": "对数据集执行完整统计分析，参数 dataset_id",
    }

    def _dispatch_builtin(self, name: str, params: dict) -> str:
        from yuanai_core.tools.data_tools import list_datasets, preview_dataset, analyze_dataset

        handlers = {
            "builtin_list_datasets": lambda: list_datasets.invoke({}),
            "builtin_preview_dataset": lambda: preview_dataset.invoke(
                {"dataset_id": params.get("dataset_id", 0)}
            ),
            "builtin_analyze_dataset": lambda: analyze_dataset.invoke(
                {"dataset_id": params.get("dataset_id", 0)}
            ),
        }
        handler = handlers.get(name)
        return handler() if handler else f"未知内置操作: {name}"
