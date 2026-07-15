"""统筹 Agent：意图识别 + 路由子 Agent + 流式回传"""

import re
import json
import asyncio
import logging
from typing import AsyncGenerator, List, Dict, Any

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from yuanai_core.core.lc import get_llm
from yuanai_core.core.schemas import ChatRequest, AgentEvent, token as ev_token, tool_start as ev_tool_start, tool_end as ev_tool_end, image_event, dashboard_event, html_event, done, error_event, reasoning, activity_event
from config.settings import AGENT_MODEL_MAP
from skills import skill_registry

logger = logging.getLogger(__name__)

ORCHESTRATOR_SYSTEM_PROMPT = """你是小元AI的助手，可以独立处理简单任务，也可以委派复杂任务给专业子Agent。

你可以直接使用的工具（简单任务，不要委派）：
- calculate_sum / calculate_multiply：计算
- get_today_temperature / get_tomorrow_forecast：天气
- get_user_memory / remember_user_info：用户记忆
- retrieve_knowledge：知识库检索
- list_data_files / read_data_file：文件操作
- get_system_stats：系统统计

只在以下情况委派给子Agent（复杂任务）：
{SKILL_LIST}

数据分析Agent有内置示例数据，以下分析无需用户提供文件即可直接执行：
- RFM客户价值分群（内置订单明细.xlsx）
- 客户流失预测（内置churn数据）
- 描述性统计分析（可指定dataset_id或使用内置数据）
- 基因表达分布分析（内置示例数据）

用户说"做RFM分析"时直接委派，不要追问文件路径。分析完成后会自动附带可视化大屏。

工作原则：
1. 判断任务复杂度：简单任务直接用工具，复杂任务委派子Agent
2. 委派时一句话说明调用哪个Agent，然后立即调用
3. 子Agent结果清晰完整时只做简短确认，不要复述
4. 需求不明确时先询问用户
5. 数据分析任务不要追问文件路径，直接委派让子Agent自行处理"""


def get_orchestrator_prompt() -> str:
    """获取动态生成的统筹提示词（自动注入当前可用的 Skill 列表）"""
    return ORCHESTRATOR_SYSTEM_PROMPT.replace(
        "{SKILL_LIST}", skill_registry.list_for_llm()
    )


def _make_delegate_tool(skill_config, orch):
    """为每个 Skill 动态创建一个 delegate 工具（闭包安全：skill_config 通过参数绑定）"""
    from langchain_core.tools import StructuredTool

    skill_name = skill_config.name
    skill_display = skill_config.display_name
    skill_desc = skill_config.description

    def delegate_fn(prompt: str) -> str:
        orch._emit_activity(f"委派{skill_display}", prompt[:80])
        agent = orch._get_or_create_agent(skill_config)
        result = agent.run(prompt)
        orch._emit_activity(f"{skill_display}已完成", "")
        return result

    return StructuredTool.from_function(
        func=delegate_fn,
        name=f"delegate_to_{skill_name}_agent",
        description=f"将复杂的{skill_desc}任务委托给{skill_display}子Agent。参数 prompt: 详细的任务需求。",
    )


class Orchestrator:
    """统筹 Agent：管理三个子 Agent，根据意图路由任务"""

    def __init__(self):
        self._analysis = None
        self._collection = None
        self._automation = None
        self._on_activity = None  # callback(activity_event) for live status updates
        self._agents = {}  # skill_name -> Agent 实例（动态创建）

    @property
    def analysis_agent(self):
        if "analysis" not in self._agents:
            from agent.agents.analysis import AnalysisAgent
            self._agents["analysis"] = AnalysisAgent()
        return self._agents["analysis"]

    @property
    def collection_agent(self):
        if "collection" not in self._agents:
            from agent.agents.collection import CollectionAgent
            self._agents["collection"] = CollectionAgent()
        return self._agents["collection"]

    @property
    def automation_agent(self):
        if "automation" not in self._agents:
            from agent.agents.automation import AutomationAgent
            self._agents["automation"] = AutomationAgent()
        return self._agents["automation"]

    def _build_all_tools(self):
        """构建完整工具列表：通用工具 + 动态生成的 delegate 工具"""
        # 通用工具（直接调用，不走子 Agent）
        from yuanai_core.tools.calculator import calculate_sum, calculate_multiply
        from yuanai_core.tools.weather import get_today_temperature, get_tomorrow_forecast
        from yuanai_core.tools.user_memory import get_user_memory, remember_user_info
        from yuanai_core.tools.knowledge_tool import retrieve_knowledge
        from yuanai_core.tools.file_tools import list_data_files, read_data_file
        from yuanai_core.tools.stats_tool import get_system_stats

        tools = [
            calculate_sum, calculate_multiply,
            get_today_temperature, get_tomorrow_forecast,
            get_user_memory, remember_user_info,
            retrieve_knowledge,
            list_data_files, read_data_file,
            get_system_stats,
        ]

        # 动态生成 delegate_* 工具（遍历 skills/ 目录自动发现）
        orch = self
        for skill in skill_registry.get_all():
            tools.append(_make_delegate_tool(skill, orch))

        return tools

    def _get_or_create_agent(self, skill_config):
        """从 Skill 配置动态创建 Agent 实例（带缓存）"""
        name = skill_config.name
        if name in self._agents:
            return self._agents[name]

        if skill_config.type == "script_dispatch":
            from agent.agents.base import ScriptDispatchAgent
            agent = ScriptDispatchAgent(skill_config)
        elif skill_config.type == "react":
            from agent.agents.automation import AutomationAgent
            agent = AutomationAgent(skill_config)
        else:
            raise ValueError(f"未知 Skill 类型: {skill_config.type} (name={name})")

        self._agents[name] = agent
        return agent

    def _emit_activity(self, message: str, detail: str = ""):
        """发送活动事件（如果 ws_client 注册了回调）"""
        if self._on_activity:
            try:
                self._on_activity(activity_event(message, detail))
            except Exception:
                pass

    async def stream(self, req: ChatRequest) -> AsyncGenerator[AgentEvent, None]:
        """流式执行统筹 Agent"""
        rid = req.request_id

        # 构建消息列表
        input_messages: List[Dict[str, Any]] = []
        for m in req.messages:
            input_messages.append(m)

        llm = get_llm(AGENT_MODEL_MAP["orchestrator"], temperature=0.7, verbose=False, streaming=True)
        orch_tools = self._build_all_tools()
        agent = create_react_agent(llm, orch_tools)

        full_response = ""
        full_reasoning = ""
        try:
            async for event in agent.astream_events({"messages": input_messages}, version="v2"):
                kind = event.get("event", "")

                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        full_response += chunk.content
                        yield ev_token(chunk.content, rid)
                    if hasattr(chunk, "reasoning_content") and chunk.reasoning_content:
                        full_reasoning += chunk.reasoning_content
                        yield reasoning(chunk.reasoning_content, rid)

                elif kind == "on_tool_start":
                    yield ev_tool_start(event.get("name", "未知工具"), rid)

                elif kind == "on_tool_end":
                    output = event["data"].get("output", "")
                    # images
                    img_urls = re.findall(r'data:image/\w+;base64,[A-Za-z0-9+/=]+', str(output))
                    for img_url in img_urls:
                        yield image_event(img_url, rid)
                    # dashboard
                    dash_match = re.search(r'__DASHBOARD__:(.+)', str(output))
                    if dash_match:
                        result_path = dash_match.group(1).strip()
                        try:
                            with open(result_path, "r", encoding="utf-8") as f:
                                dash_data = json.load(f)
                            cache_key = f"dashboard:{req.session_id}"
                            try:
                                from db.redis_client import get_redis
                                rds = get_redis()
                                rds.setex(cache_key, 3600, json.dumps(dash_data, ensure_ascii=False))
                            except Exception:
                                pass
                            yield dashboard_event(req.session_id, rid)
                        except Exception as e:
                            logger.warning("dashboard parse failed: %s", e)
                    # HTML (plotly interactive charts)
                    html_match = re.search(r'__HTML__URL:(.+)', str(output))
                    if html_match:
                        for url in html_match.group(1).split(","):
                            yield html_event(url.strip(), rid)
                    # clean
                    clean_output = re.sub(r',data:image/\w+;base64,[A-Za-z0-9+/=]+', '', str(output))
                    clean_output = re.sub(r'\n__DASHBOARD__:\S+', '', clean_output)
                    clean_output = re.sub(r'\n__HTML__URL:\S+', '', clean_output).strip()
                    yield ev_tool_end(event.get("name", "未知工具"), clean_output, rid)

            yield done(full_response, full_reasoning, rid)
        except Exception as e:
            logger.error("统筹 Agent 异常: %s", e, exc_info=True)
            yield error_event(str(e), rid)
