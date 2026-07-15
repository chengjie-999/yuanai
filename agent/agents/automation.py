"""自动化子 Agent：浏览器控制 + 题目审核 + 截图监控。
配置从 skills/automation/skill.yaml 加载。"""

import logging
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from yuanai_core.core.lc import get_llm
from agent.tools import load_agent_tools
from agent.agents.base import AgentBase

logger = logging.getLogger(__name__)


class AutomationAgent(AgentBase):
    """支持两种初始化方式：
    1. AutomationAgent() — 从 skills/automation/skill.yaml 自动加载（推荐）
    2. AutomationAgent(skill_config) — 从传入的 SkillConfig 加载（Orchestrator 使用）"""

    def __init__(self, skill_config=None):
        super().__init__()
        if skill_config is not None:
            self.name = skill_config.name
            self.model_name = skill_config.model
            self._system_prompt = skill_config.system_prompt
        else:
            from skills import skill_registry
            cfg = skill_registry.get("automation")
            if cfg:
                self.name = cfg.name
                self.model_name = cfg.model
                self._system_prompt = cfg.system_prompt
            else:
                self.name = "automation"
                self.model_name = "doubao-seed-2-0-pro"
                self._system_prompt = ""
        self._tools = None

    @property
    def tools(self):
        if self._tools is None:
            self._tools = load_agent_tools()
        return self._tools

    def run(self, prompt: str) -> str:
        llm = get_llm(self.model_name, temperature=0.3, verbose=False)
        agent = create_react_agent(llm, self.tools)
        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=prompt),
        ]
        try:
            result = agent.invoke({"messages": messages})
            return result["messages"][-1].content
        except Exception as e:
            logger.error("自动化 Agent 异常: %s", e)
            return f"自动化操作失败: {e}"
