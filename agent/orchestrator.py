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
from yuanai_core.core.schemas import ChatRequest, AgentEvent, token as ev_token, tool_start as ev_tool_start, tool_end as ev_tool_end, image_event, done, error_event, reasoning, activity_event

logger = logging.getLogger(__name__)

ORCHESTRATOR_SYSTEM_PROMPT = """你是小元AI的统筹助手，管理着三个专业子Agent团队。

你的子Agent团队：
- delegate_to_analysis_agent：数据分析（数据集管理、统计、图表）
- delegate_to_collection_agent：数据采集（网页爬取、内容抓取）
- delegate_to_automation_agent：自动化（浏览器控制、题目审核）

工作原则：
1. 收到用户请求后，先判断需要哪个子Agent
2. 用一句话告知用户将调用哪个子Agent，然后立刻调用它
3. 子Agent返回结果后，如果结果已经清晰完整，只做简短确认如"以上是分析结果"，不要再复述一遍
4. 只有当结果需要解读、比较、给出建议时，才补充分析
5. 复杂任务分步进行：先采集再分析，先浏览再审核
6. 需求不明确时，先询问用户再行动

重要：用户能看到子Agent的输出，重复同样的内容只会让对话冗余。只补充子Agent没说的内容。"""


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

    def _build_delegate_tools(self):
        """构建委托工具列表"""
        orch = self

        @tool
        def delegate_to_analysis_agent(prompt: str) -> str:
            """将数据分析任务委托给数据分析子Agent。参数 prompt: 详细的数据分析需求描述（包含要分析的文件名、分析类型等）。返回分析结果。"""
            orch._emit_activity("委派数据分析Agent", prompt[:80])
            result = orch.analysis_agent.run(prompt)
            orch._emit_activity("数据分析Agent已完成", "")
            return result

        @tool
        def delegate_to_collection_agent(prompt: str) -> str:
            """将数据采集任务委托给数据采集子Agent。参数 prompt: 详细的数据采集需求描述（包含目标网址、要抓取的数据等）。返回采集结果。"""
            orch._emit_activity("委派数据采集Agent", prompt[:80])
            result = orch.collection_agent.run(prompt)
            orch._emit_activity("数据采集Agent已完成", "")
            return result

        @tool
        def delegate_to_automation_agent(prompt: str) -> str:
            """将自动化/审核任务委托给自动化子Agent。参数 prompt: 详细的自动化需求描述（包含审核对象、操作步骤等）。返回执行结果。"""
            orch._emit_activity("委派自动化Agent", prompt[:80])
            result = orch.automation_agent.run(prompt)
            orch._emit_activity("自动化Agent已完成", "")
            return result

        return [
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
        orch_tools = self._build_delegate_tools()
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
                    img_urls = re.findall(r'data:image/\w+;base64,[A-Za-z0-9+/=]+', str(output))
                    for img_url in img_urls:
                        yield image_event(img_url, rid)
                    clean_output = re.sub(r',data:image/\w+;base64,[A-Za-z0-9+/=]+', '', str(output))
                    yield ev_tool_end(event.get("name", "未知工具"), clean_output, rid)

            yield done(full_response, full_reasoning, rid)
        except Exception as e:
            logger.error("统筹 Agent 异常: %s", e, exc_info=True)
            yield error_event(str(e), rid)
