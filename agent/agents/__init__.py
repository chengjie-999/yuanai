"""Agent 注册表 — 新增 Agent 类型只需在此注册即可被 Orchestrator 自动发现"""
from agent.agents.base import AgentBase
from agent.agents.analysis import AnalysisAgent
from agent.agents.collection import CollectionAgent
from agent.agents.automation import AutomationAgent

AGENT_REGISTRY: dict[str, type[AgentBase]] = {
    "analysis": AnalysisAgent,
    "collection": CollectionAgent,
    "automation": AutomationAgent,
}
