"""Agent 注册表（融合后仅 automation 保留独立子 Agent；脚本类能力已工具化进统筹）"""
from agent.agents.base import AgentBase
from agent.agents.automation import AutomationAgent

AGENT_REGISTRY: dict[str, type[AgentBase]] = {
    "automation": AutomationAgent,
}
