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

你可以直接使用的工具：
- 计算器：calculate_sum / calculate_multiply
- 天气：get_today_temperature / get_tomorrow_forecast
- 用户记忆：get_user_memory / remember_user_info
- 知识库：retrieve_knowledge
- 文件操作：list_data_files / read_data_file / save_data_csv
- 系统统计：get_system_stats
- 数据集管理：list_datasets / preview_dataset / analyze_dataset / transform_dataset
- 网页爬取：fetch_url / parse_html / save_crawl_data / list_crawl_data / get_crawl_detail

仅在以下情况委派给子Agent（复杂任务）：
{SKILL_LIST}

工作原则：
1. 简单操作直接用工具（查数据集、爬网页、读文件等），不要委派
2. 复杂分析/采集才委派子Agent
3. 委派时简短说明意图，不要长篇解释
4. 子Agent结果直接呈现用户，不再复述
5. 数据分析优先用 list_datasets + preview_dataset 确认数据，简单统计直接用 analyze_dataset，复杂分析才委派"""


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
        """构建完整工具列表：全部共享工具 + 动态生成的 delegate 工具"""
        from yuanai_core.tools import all_tools

        tools = list(all_tools)

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

    def _build_tools_for_intent(self, intent) -> list:
        """按意图分类动态加载工具子集（大幅节省 token）"""
        from agent.intent_classifier import IntentClassifier, INTENT_TOOL_GROUPS
        from yuanai_core.tools import load_tools_for

        categories = IntentClassifier.get_tool_categories(intent)
        tools = []
        has_general = False
        has_delegate_all = False

        for cat in categories:
            if cat == "delegate_all":
                has_delegate_all = True
            elif cat.startswith("delegate_"):
                if not has_general:
                    tools.extend(load_tools_for("general", "memory", "knowledge"))
                    has_general = True
                skill_name = cat.replace("delegate_", "")
                skill = skill_registry.get(skill_name)
                if skill:
                    tools.append(_make_delegate_tool(skill, self))
            elif cat == "general":
                if not has_general:
                    tools.extend(load_tools_for("general"))
                    has_general = True
            else:
                tools.extend(load_tools_for(cat))

        if has_delegate_all:
            if not has_general:
                tools.extend(load_tools_for("general", "memory", "knowledge"))
                has_general = True
            orch = self
            for skill in skill_registry.get_all():
                found = any(t.name == f"delegate_to_{skill.name}_agent" for t in tools)
                if not found:
                    tools.append(_make_delegate_tool(skill, orch))

        return tools

    def _handle_direct_command(self, intent, message: str) -> str:
        """直接执行命令，完全跳过 LLM（100% token 节省）"""
        msg = message.strip().replace(" ", "").replace("　", "")

        # 算术
        import re as _re
        nums = _re.findall(r'[\d\.]+', msg)
        if len(nums) >= 2:
            a, b = float(nums[0]), float(nums[1])
            try:
                if any(op in msg for op in ('+', '＋')):
                    from yuanai_core.tools.calculator import calculate_sum
                    return str(calculate_sum.invoke({"a": a, "b": b}))
                if any(op in msg for op in ('*', '×')):
                    from yuanai_core.tools.calculator import calculate_multiply
                    return str(calculate_multiply.invoke({"a": a, "b": b}))
                if any(op in msg for op in ('/', '÷')):
                    from yuanai_core.tools.calculator import calculate_divide
                    return str(calculate_divide.invoke({"a": a, "b": b}))
                if any(op in msg for op in ('-', '－')):
                    from yuanai_core.tools.calculator import calculate_sum
                    return str(calculate_sum.invoke({"a": a, "b": -b}))
            except Exception as e:
                return f"计算失败: {e}"

        # 日期/时间
        if "星期几" in msg:
            from yuanai_core.tools.datetime_tools import get_weekday
            return get_weekday.invoke({})
        if any(w in msg for w in ("几点", "几点了", "当前时间")):
            from yuanai_core.tools.datetime_tools import get_current_time
            return get_current_time.invoke({"format": "%Y-%m-%d %H:%M:%S"})

        return "无法直接处理，请重新描述需求"

    def _extract_latest_message(self, messages: list) -> str:
        """从消息列表中提取最新用户消息文本。"""
        for m in reversed(messages):
            if isinstance(m, dict):
                if m.get("role") == "user":
                    return m.get("content", "")
            elif hasattr(m, "type") and m.type == "human":
                return m.content if hasattr(m, "content") else str(m)
        return ""

    async def stream(self, req: ChatRequest) -> AsyncGenerator[AgentEvent, None]:
        """两级路由：意图分类 → 动态加载工具子集 → 流式执行"""
        rid = req.request_id

        # 构建消息列表
        input_messages: List[Dict[str, Any]] = []
        for m in req.messages:
            input_messages.append(m)

        # ---- Tier 1: 意图分类（零 API 成本）----
        latest_msg = self._extract_latest_message(input_messages)
        from agent.intent_classifier import classifier as intent_clf
        intent = intent_clf.classify(latest_msg)

        logger.info("意图分类: %s (置信度 %.2f, 消息前50字: %s)",
                    intent.group, intent.confidence, latest_msg[:50])

        # ---- Tier 1.5: 低置信度降级到 mini LLM 分类 ----
        if intent_clf.needs_fallback_llm(intent) and latest_msg:
            try:
                from agent.intent_classifier import LLM_CLASSIFIER_PROMPT
                fallback_llm = get_llm(AGENT_MODEL_MAP["orchestrator"],
                                       temperature=0, verbose=False, streaming=False)
                resp = fallback_llm.invoke([
                    SystemMessage(content=LLM_CLASSIFIER_PROMPT.format(message=latest_msg)),
                ])
                fb = resp.content.strip().lower() if hasattr(resp, "content") else ""
                for group in INTENT_TOOL_GROUPS:
                    if group in fb:
                        intent = intent_clf.__class__.__new__(intent_clf.__class__)
                        intent.group = group
                        intent.confidence = 0.7
                        intent.is_direct = False
                        logger.info("LLM 降级分类 → %s", group)
                        break
            except Exception as e:
                logger.debug("LLM 降级分类失败: %s", e)

        # ---- Tier 2: 直接命令（绕过 LLM）----
        if intent.is_direct:
            try:
                result = self._handle_direct_command(intent, latest_msg)
                logger.info("直接命令执行结果: %s", result[:100])
                yield done(result, "", rid)
                return
            except Exception as e:
                logger.warning("直接命令失败，回退 LLM: %s", e)

        # ---- Tier 3: 动态加载工具子集 + LLM ----
        orch_tools = self._build_tools_for_intent(intent)
        logger.info("加载 %d 个工具 (意图: %s)", len(orch_tools), intent.group)

        # 图片识别 → 自动切换到视觉模型（DeepSeek V4 不支持图片）
        has_images = bool(req.images) or any(
            isinstance(m.get("content"), list) and
            any(c.get("type") == "image_url" for c in m["content"] if isinstance(c, dict))
            for m in input_messages if isinstance(m, dict)
        )
        orch_model = AGENT_MODEL_MAP["orchestrator"]
        if has_images and "deepseek" in orch_model:
            from config.settings import VISION_MODEL
            orch_model = VISION_MODEL
            logger.info("检测到图片，自动切换到视觉模型: %s", orch_model)

        llm = get_llm(orch_model, temperature=0.7, verbose=False, streaming=True)
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
                    rc = chunk.additional_kwargs.get("reasoning_content", "") if hasattr(chunk, "additional_kwargs") else ""
                    if not rc:
                        rc = getattr(chunk, "reasoning_content", "")
                    if rc:
                        full_reasoning += rc
                        yield reasoning(rc, rid)

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
