"""数据采集 Agent：LLM 意图匹配 → 派发爬虫脚本"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from yuanai_core.core.lc import get_llm
from agent.scripts.registry import ScriptRegistry

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是数据采集专家。根据用户需求，从可用脚本列表中选择最合适的，提取参数。

返回 JSON 格式（只返回 JSON，不要其他文字）：
{"script": "脚本名", "params": {"参数名": "值"}}
如果无法匹配任何脚本，返回：
{"script": null, "reason": "原因"}
如果用户没提供必要的参数（如 URL），在 reason 中说明要用户补充什么。"""


class CollectionAgent:
    def __init__(self):
        self.registry = ScriptRegistry("agent.datanalysis.crawl")

    def run(self, prompt: str) -> str:
        script_list = self.registry.list_for_llm()

        if "暂无可用脚本" in script_list:
            return "⚠️ 暂无可用采集脚本，请先在 agent/scripts/crawl/ 下添加脚本。"

        llm = get_llm("doubao-seed-2-0-lite-260215", temperature=0, verbose=False)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"可用脚本：\n{script_list}\n\n用户需求：{prompt}"),
        ]
        response = llm.invoke(messages)

        # 解析 LLM 返回的 JSON
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

        return self.registry.run(choice["script"], **choice.get("params", {}))
