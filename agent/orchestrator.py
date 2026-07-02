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
from yuanai_core.core.schemas import ChatRequest, AgentEvent, token as ev_token, tool_start as ev_tool_start, tool_end as ev_tool_end, image_event, dashboard_event, done, error_event, reasoning, activity_event

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
- delegate_to_analysis_agent：数据分析（统计、图表生成等复杂操作）
- delegate_to_collection_agent：数据采集（多页爬取、复杂抓取）
- delegate_to_automation_agent：自动化（浏览器控制、题目审核）

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


class Orchestrator:
    """统筹 Agent：管理三个子 Agent，根据意图路由任务"""

    def __init__(self):
        self._analysis = None
        self._collection = None
        self._automation = None
        self._on_activity = None  # callback(activity_event) for live status updates

    @property
    def analysis_agent(self):
        if self._analysis is None:
            from agent.agents.analysis import AnalysisAgent
            self._analysis = AnalysisAgent()
        return self._analysis

    @property
    def collection_agent(self):
        if self._collection is None:
            from agent.agents.collection import CollectionAgent
            self._collection = CollectionAgent()
        return self._collection

    @property
    def automation_agent(self):
        if self._automation is None:
            from agent.agents.automation import AutomationAgent
            self._automation = AutomationAgent()
        return self._automation

    def _build_all_tools(self):
        """构建完整工具列表：通用工具 + 3 个委托工具"""
        # 通用工具（直接调用，不走子 Agent）
        from yuanai_core.tools.calculator import calculate_sum, calculate_multiply
        from yuanai_core.tools.weather import get_today_temperature, get_tomorrow_forecast
        from yuanai_core.tools.user_memory import get_user_memory, remember_user_info
        from yuanai_core.tools.knowledge_tool import retrieve_knowledge
        from yuanai_core.tools.file_tools import list_data_files, read_data_file
        from yuanai_core.tools.stats_tool import get_system_stats

        orch = self

        @tool
        def delegate_to_analysis_agent(prompt: str) -> str:
            """将复杂的数据分析任务（如统计分析、生成图表）委托给数据分析子Agent。简单的列举数据集、预览数据请直接用 list_datasets 等工具，不要调用此委托。参数 prompt: 详细的分析需求。"""
            orch._emit_activity("委派数据分析Agent", prompt[:80])
            result = orch.analysis_agent.run(prompt)
            orch._emit_activity("数据分析Agent已完成", "")
            return result

        @tool
        def delegate_to_collection_agent(prompt: str) -> str:
            """将复杂的网页数据采集任务委托给数据采集子Agent。简单的抓取/解析直接用 fetch_url/parse_html 工具。参数 prompt: 详细的采集需求。"""
            orch._emit_activity("委派数据采集Agent", prompt[:80])
            result = orch.collection_agent.run(prompt)
            orch._emit_activity("数据采集Agent已完成", "")
            return result

        @tool
        def delegate_to_automation_agent(prompt: str) -> str:
            """将复杂的浏览器自动化任务（如题目审核、多步操作）委托给自动化子Agent。参数 prompt: 详细的自动化需求。"""
            orch._emit_activity("委派自动化Agent", prompt[:80])
            result = orch.automation_agent.run(prompt)
            orch._emit_activity("自动化Agent已完成", "")
            return result

        return [
            # 通用工具 — 简单任务直接调，不要委托给子 Agent
            calculate_sum, calculate_multiply,
            get_today_temperature, get_tomorrow_forecast,
            get_user_memory, remember_user_info,
            retrieve_knowledge,
            list_data_files, read_data_file,
            get_system_stats,
            # 委托工具 — 复杂领域任务才用
            delegate_to_analysis_agent,
            delegate_to_collection_agent,
            delegate_to_automation_agent,
        ]

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

        llm = get_llm("doubao-seed-2-0-lite-260215", temperature=0.7, verbose=False, streaming=True)
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
                    # clean
                    clean_output = re.sub(r',data:image/\w+;base64,[A-Za-z0-9+/=]+', '', str(output))
                    clean_output = re.sub(r'\n__DASHBOARD__:\S+', '', clean_output).strip()
                    yield ev_tool_end(event.get("name", "未知工具"), clean_output, rid)

            yield done(full_response, full_reasoning, rid)
        except Exception as e:
            logger.error("统筹 Agent 异常: %s", e, exc_info=True)
            yield error_event(str(e), rid)
