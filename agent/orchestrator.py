"""统筹 Agent：意图识别 + 路由子 Agent + 流式回传"""

import re
import json
import asyncio
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from yuanai_core.core.lc import get_llm
from yuanai_core.core.schemas import ChatRequest, AgentEvent, token as ev_token, tool_start as ev_tool_start, tool_end as ev_tool_end, image_event, dashboard_event, html_event, done, error_event, reasoning, activity_event
from config.settings import AGENT_MODEL_MAP
from skills import skill_registry

logger = logging.getLogger(__name__)

def _tool_sender(name: str) -> str:
    """工具归属推断（信封协议）：delegate_to_xxx_agent → xxx；其余（含计划工具）→ orchestrator。

    计划工具不独立成气泡（用户拍板）：工具卡挂统筹气泡，计划入口走顶栏「计划」tab。
    """
    if name.startswith("delegate_to_") and name.endswith("_agent"):
        skill = name[len("delegate_to_"):-len("_agent")]
        if skill in ("analysis", "collection", "automation", "claude"):
            return skill
    return "orchestrator"


def _make_automation_delegate_tool(orch):
    """自动化是唯一保留的独立子 Agent（react 多步自主）；脚本类能力已工具化进统筹"""
    from langchain_core.tools import StructuredTool

    skill_config = skill_registry.get("automation")
    if not skill_config:
        return None

    def delegate_fn(prompt: str) -> str:
        from yuanai_core.core.schemas import progress
        from yuanai_core.rag import current_request_id
        orch._emit_activity(f"委派{skill_config.display_name}", prompt[:80])
        agent = orch._get_or_create_agent(skill_config)
        rid = current_request_id.get() or ""
        progress_cb = lambda cur, total, msg: orch._emit_event(progress(cur, total, msg, rid))  # noqa: E731
        result = agent.run(prompt, progress_cb=progress_cb)
        orch._emit_activity(f"{skill_config.display_name}已完成", "")
        return result

    return StructuredTool.from_function(
        func=delegate_fn,
        name="delegate_to_automation_agent",
        description=f"将需要浏览器控制/多步自主操作的复杂任务委托给{skill_config.display_name}子Agent。参数 prompt: 详细的任务需求。",
    )


class Orchestrator:
    """统筹 Agent：脚本工具直调 + automation 唯一子 Agent + Claude Code 桥接"""

    def __init__(self, enabled_skills: Optional[List[str]] = None, enable_claude: bool = True):
        """enabled_skills=None 表示全部启用；否则只启用列表内的 skill（脚本工具按此过滤）。
        enable_claude 控制本机 Claude Code 委派。"""
        self._on_activity = None  # callback(activity_event) for live status updates
        self._on_event = None  # callback(event) 任意事件上报（如工具内 progress 心跳）
        self._agents = {}  # skill_name -> Agent 实例（动态创建，现在只剩 automation）
        self._enabled_skills = enabled_skills
        self._enable_claude = enable_claude

    def _skill_enabled(self, name: str) -> bool:
        return self._enabled_skills is None or name in self._enabled_skills

    def cancel_request(self, request_id: str):
        """B1-12 停止生成联动：终止该请求正在运行的脚本子进程（云端 stop 事件到达时调用）"""
        try:
            from agent.scripts.registry import cancel_running
            n = cancel_running(request_id)
            if n:
                logger.info("停止联动：已终止 %d 个脚本子进程 (req=%s)", n, request_id[:8])
        except Exception as e:
            logger.warning("cancel_request 失败: %s", e)

    @property
    def automation_agent(self):
        if "automation" not in self._agents:
            from agent.agents.automation import AutomationAgent
            self._agents["automation"] = AutomationAgent(skill_registry.get("automation"))
        return self._agents["automation"]

    def _get_or_create_agent(self, skill_config):
        """从 Skill 配置创建 Agent 实例（带缓存）；融合后仅 automation（react）"""
        name = skill_config.name
        if name in self._agents:
            return self._agents[name]
        if skill_config.type != "react":
            raise ValueError(f"未知 Skill 类型: {skill_config.type} (name={name})（脚本类已工具化）")
        from agent.agents.automation import AutomationAgent
        agent = AutomationAgent(skill_config)
        self._agents[name] = agent
        return agent

    def _emit_activity(self, message: str, detail: str = ""):
        """发送活动事件（如果 ws_client 注册了回调）"""
        if self._on_activity:
            try:
                self._on_activity(activity_event(message, detail))
            except Exception:
                pass

    def _emit_event(self, event):
        """发送任意事件（如工具内 progress 心跳）（如果 ws_client 注册了回调）"""
        if self._on_event:
            try:
                self._on_event(event)
            except Exception:
                pass

    def _make_claude_tool(self):
        """创建 delegate_to_claude_agent 工具（emit 回调节点：工具内进度心跳 → 云端）"""
        from agent.tools.claude_delegate import make_claude_tool
        return make_claude_tool(lambda ev: self._emit_event(ev))

    def _build_tools_for_intent(self, intent) -> list:
        """按意图分类动态加载工具子集（大幅节省 token）。

        融合后类别 token：scripts_analysis/scripts_collection/scripts_all =
        脚本工具（registry 生成）；delegate_automation = automation 子 Agent；
        delegate_all = scripts_all + automation + claude（语义重定义）。
        """
        from agent.intent_classifier import IntentClassifier, INTENT_TOOL_GROUPS
        from agent.scripts.tools import build_script_tools, get_registry
        from yuanai_core.tools import load_tools_for

        categories = IntentClassifier.get_tool_categories(intent)
        tools = []
        has_general = False
        has_delegate_all = False

        def ensure_general():
            nonlocal has_general
            if not has_general:
                tools.extend(load_tools_for("general", "memory", "knowledge"))
                has_general = True

        def add_script_tools(skill_name: str):
            registry = get_registry(skill_name)
            if registry and self._skill_enabled(skill_name):
                tools.extend(build_script_tools(
                    registry, skill=skill_name,
                    progress_cb=self._script_progress_cb()))

        def _add_claude():
            if self._enable_claude:
                tools.append(self._make_claude_tool())

        for cat in categories:
            if cat == "delegate_all":
                has_delegate_all = True
            elif cat == "delegate_claude":
                ensure_general()
                _add_claude()
            elif cat == "delegate_automation":
                ensure_general()
                if self._skill_enabled("automation"):
                    tools.append(_make_automation_delegate_tool(self))
            elif cat == "scripts_analysis":
                add_script_tools("analysis")
            elif cat == "scripts_collection":
                add_script_tools("collection")
            elif cat == "scripts_all":
                add_script_tools("analysis")
                add_script_tools("collection")
            elif cat == "general":
                ensure_general()
            else:
                tools.extend(load_tools_for(cat))

        if has_delegate_all:
            ensure_general()
            add_script_tools("analysis")
            add_script_tools("collection")
            if self._skill_enabled("automation"):
                tools.append(_make_automation_delegate_tool(self))
            _add_claude()

        return tools

    def _script_progress_cb(self):
        """脚本工具进度回调 → 云端 SSE progress 事件（10s 心跳重置 300s 超时）"""
        from yuanai_core.core.schemas import progress
        from yuanai_core.rag import current_request_id

        def cb(cur, total, msg):
            self._emit_event(progress(cur, total, msg, current_request_id.get() or ""))
        return cb

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

    def _extract_tool_output(self, output: str, session_id: str, rid: str, tool_name: str = ""):
        """提取 delegate 工具输出协议（图片/大屏/HTML），返回 (事件列表, 清洗后文本)

        B0（2026-10-17）：统一走 A 看板——32hex 看板 key 存在即只发一个带
        dashboard_html 的 dashboard 事件（首次/缓存命中同一入口）；文件路径
        JSON 仍缓存 Redis/落库供通用大屏历史数据，但不再抢占事件入口。
        """
        events = []
        img_urls = re.findall(r'data:image/\w+;base64,[A-Za-z0-9+/=]+', str(output))
        for img_url in img_urls:
            events.append(image_event(img_url, rid))
        # __DASHBOARD__ 两态：文件路径（__RESULT__ JSON，缓存 Redis + 落库）与
        # 32hex 看板缓存 key（A 看板，前端开 /chat/agent/board 轻量页）
        dash_html_url = ""
        sent_dashboard = False
        for dash_match in re.finditer(r'__DASHBOARD__:(.+)', str(output)):
            value = dash_match.group(1).strip()
            if re.fullmatch(r'[0-9a-f]{32}', value):
                # 看板 key 存在 → 统一入口挂看板（首次与缓存命中同一形态）
                dash_html_url = f"/api/v1/data/dashboard-html/{value}"
                if not sent_dashboard:
                    events.append(dashboard_event(session_id, rid, dashboard_html=dash_html_url))
                    sent_dashboard = True
                continue
            try:
                with open(value, "r", encoding="utf-8") as f:
                    dash_data = json.load(f)
                cache_key = f"dashboard:{session_id}"
                try:
                    from db.redis_client import get_redis
                    rds = get_redis()
                    rds.setex(cache_key, 3600, json.dumps(dash_data, ensure_ascii=False))
                except Exception:
                    pass
                # 持久化到 analysis_history（Redis TTL 过期后恢复用；带脚本名）
                try:
                    from db.session import get_db as _db
                    _db().add_analysis_history(session_id, json.dumps(dash_data, ensure_ascii=False),
                                               script_name=tool_name)
                except Exception as e:
                    logger.warning("analysis history persist failed: %s", e)
                if not sent_dashboard:
                    # 纯 JSON 无看板 → 原大屏事件
                    events.append(dashboard_event(session_id, rid))
                    sent_dashboard = True
            except Exception as e:
                logger.warning("dashboard parse failed: %s", e)
        html_match = re.search(r'__HTML__URL:(.+)', str(output))
        if html_match:
            for url in html_match.group(1).split(","):
                events.append(html_event(url.strip(), rid))
        clean_output = re.sub(r',data:image/\w+;base64,[A-Za-z0-9+/=]+', '', str(output))
        clean_output = re.sub(r'\n__DASHBOARD__:\S+', '', clean_output)
        clean_output = re.sub(r'\n__HTML__URL:\S+', '', clean_output).strip()
        return events, clean_output

    async def stream_target(self, req: ChatRequest, skill_name: str) -> AsyncGenerator[AgentEvent, None]:
        """确定性分派：@指定子 Agent 时跳过统筹 LLM，直接调对应 skill Agent。

        融合后仅 automation 保留（脚本类能力已工具化进统筹，@面板不再有
        分析/采集）；与 mode=claude 桥接分支同构（agent/main.py route 调用）。
        """
        rid = req.request_id
        if skill_name != "automation":
            yield error_event(f"未找到技能: {skill_name}", rid)
            return
        cfg = skill_registry.get(skill_name)
        if not cfg:
            yield error_event(f"未找到技能: {skill_name}", rid)
            return
        if not self._skill_enabled(skill_name):
            yield error_event(f"{cfg.display_name}未启用（请在托盘菜单开启对应 Agent 开关）", rid)
            return
        agent = self._get_or_create_agent(cfg)
        # 视图滤波：子 Agent 只看到定向上下文（别人的话给摘要，自己的身份清楚）；
        # 整条流的身份由前端占位气泡 sender=target 承担，无需 sender_event
        from yuanai_core.core.views import view_for, compose_target_prompt
        view = view_for(skill_name, req.messages, envelopes=getattr(req, "envelopes", []) or [])
        prompt = compose_target_prompt(view) or self._extract_latest_message(req.messages)
        self._emit_activity(f"委派{cfg.display_name}", prompt[:80])
        from yuanai_core.core.schemas import progress
        from yuanai_core.rag import current_request_id
        rid_ctx = current_request_id.get() or ""
        progress_cb = lambda cur, total, msg: self._emit_event(progress(cur, total, msg, rid_ctx))  # noqa: E731
        try:
            result = await asyncio.to_thread(agent.run, prompt, progress_cb=progress_cb)
        except Exception as e:
            logger.error("定向分派 %s 异常: %s", skill_name, e, exc_info=True)
            yield error_event(str(e), rid)
            return
        self._emit_activity(f"{cfg.display_name}已完成", "")
        events, clean = self._extract_tool_output(result, req.session_id, rid)
        for ev in events:
            yield ev
        yield ev_token(clean, rid)
        yield done(clean, "", rid)

    async def stream(self, req: ChatRequest) -> AsyncGenerator[AgentEvent, None]:
        """两级路由：意图分类 → 动态加载工具子集 → 流式执行"""
        rid = req.request_id

        # 构建消息列表：视图滤波（统筹视角）——别人的话摘要/前缀、自己的话原样；
        # 信封全空时 view_for 退化直通（= 旧行为）。输出只取 role/content/tool_calls，
        # 剥掉信封键防 LangGraph 校验意外。
        from yuanai_core.core.views import view_for
        view = view_for("orchestrator", req.messages, self_senders={"local"},
                        envelopes=getattr(req, "envelopes", []) or [])
        input_messages: List[Dict[str, Any]] = []
        for v in view:
            item = {"role": v.get("role", ""), "content": v.get("content", "")}
            if v.get("tool_calls"):
                item["tool_calls"] = v["tool_calls"]
            if v.get("tool_call_id"):
                item["tool_call_id"] = v["tool_call_id"]
            input_messages.append(item)

        # ---- Tier 1: 意图分类（零 API 成本）----
        latest_msg = self._extract_latest_message(input_messages)
        # 2026-10-19 修复：带图片请求 content 是 list（chat.py 构造多模态），
        # classify 里 .strip() 抛 AttributeError → 取纯文本部分
        if isinstance(latest_msg, list):
            latest_msg = "".join(
                str(c.get("text", "")) if isinstance(c, dict) else str(c)
                for c in latest_msg)
        from agent.intent_classifier import classifier as intent_clf
        intent = intent_clf.classify(latest_msg)

        logger.info("意图分类: %s (置信度 %.2f, 消息前50字: %s)",
                    intent.group, intent.confidence, latest_msg[:50])

        # ---- Tier 1.5: 低置信度降级到 mini LLM 分类 ----
        if intent_clf.needs_fallback_llm(intent) and latest_msg:
            try:
                from agent.intent_classifier import LLM_CLASSIFIER_PROMPT, INTENT_TOOL_GROUPS
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
                # 2026-10-19：此前 NameError（INTENT_TOOL_GROUPS 未导入）被 debug 吞掉，
                # 降级分类永久哑火——修复导入后用 warning 记录真实失败
                logger.warning("LLM 降级分类失败: %s", e)

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

        # 图片识别（2026-10-16 收窄）：DeepSeek V4.1 Flash 原生支持图像输入，
        # 豆包全系多模态——只有不支持图片的 deepseek-v4-pro 才切豆包（切换有延迟）
        has_images = bool(req.images) or any(
            isinstance(m.get("content"), list) and
            any(c.get("type") == "image_url" for c in m["content"] if isinstance(c, dict))
            for m in input_messages if isinstance(m, dict)
        )
        orch_model = AGENT_MODEL_MAP["orchestrator"]
        if has_images and orch_model == "deepseek-v4-pro":
            from config.settings import VISION_MODEL
            orch_model = VISION_MODEL
            logger.info("检测到图片，自动切换到视觉模型: %s", orch_model)

        # 模型如实自报（2026-10-16 起，2026-10-17 修正）：
        # - resolve_model_id 归一化 + 后台设定中心模板（模型 ID 运行时真值填充）
        # - 追加进已有首条 system 消息（云端已下发前端提示）而非 insert 双 system
        from yuanai_core.core.lc import resolve_model_id
        from config.settings import self_report_text
        self_report = "\n\n" + self_report_text(resolve_model_id(orch_model))
        # 能力边界身份卡（docs/agents/orchestrator.md，单一事实源）：让统筹知道自己
        # 能做什么（脚本直调/搜索/计划/委派）与不能做什么（边界），同处追加
        from yuanai_core.agent_docs import agent_doc
        _doc = agent_doc("orchestrator")
        if _doc:
            self_report += "\n\n" + _doc
        if input_messages and input_messages[0].get("role") == "system":
            input_messages[0]["content"] = (input_messages[0].get("content") or "") + self_report
        else:
            input_messages.insert(0, {"role": "system", "content": self_report.strip()})
        llm = get_llm(orch_model, temperature=0.7, verbose=False, streaming=True)
        # 同名工具单轮 ≤3 次护栏（与云端 limited_tools 同口径）+ 显式轮数上限
        from yuanai_core.core.chat import limited_tools
        orch_tools = limited_tools(orch_tools)
        agent = create_react_agent(llm, orch_tools)

        full_response = ""
        full_reasoning = ""
        from yuanai_core.core.chat import feed_dsml, flush_dsml, dsml_filters, dsml_saw_block
        filters = dsml_filters()   # DSML 抑制：run_id → (content, reasoning) 过滤器
        saw_tool = False           # 本轮是否有结构化工具调用（配合 DSML 抑制兜底）
        try:
            async for event in agent.astream_events(
                    {"messages": input_messages}, version="v2",
                    config={"recursion_limit": 25}):
                kind = event.get("event", "")
                run_id = event.get("run_id", "")

                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        clean = feed_dsml(filters, run_id, "content", chunk.content)
                        if clean:
                            full_response += clean
                            yield ev_token(clean, rid)
                    rc = chunk.additional_kwargs.get("reasoning_content", "") if hasattr(chunk, "additional_kwargs") else ""
                    if not rc:
                        rc = getattr(chunk, "reasoning_content", "")
                    if rc:
                        rclean = feed_dsml(filters, run_id, "reasoning", rc)
                        if rclean:
                            full_reasoning += rclean
                            yield reasoning(rclean, rid)

                elif kind == "on_chat_model_end":
                    tail = flush_dsml(filters, run_id, "content")
                    if tail:
                        full_response += tail
                        yield ev_token(tail, rid)
                    rtail = flush_dsml(filters, run_id, "reasoning")
                    if rtail:
                        full_reasoning += rtail
                        yield reasoning(rtail, rid)

                elif kind == "on_tool_start":
                    saw_tool = True
                    name = event.get("name", "未知工具")
                    yield ev_tool_start(name, rid, sender=_tool_sender(name),
                                        args=(event.get("data") or {}).get("input"))

                elif kind == "on_tool_end":
                    name = event.get("name", "未知工具")
                    from yuanai_core.core.chat import _tool_output_str
                    output = _tool_output_str(event["data"].get("output", ""))
                    # B0：脚本失败协议（__ERROR__: 前缀）→ tool_end 数据带 error 标记
                    is_error = str(output).startswith("__ERROR__:")
                    if is_error:
                        output = str(output)[len("__ERROR__:"):]
                    events, clean_output = self._extract_tool_output(output, req.session_id, rid, tool_name=name)
                    for ev in events:
                        yield ev
                    if is_error:
                        yield ev_tool_end(name, clean_output, rid, sender=_tool_sender(name), is_error=True)
                    else:
                        yield ev_tool_end(name, clean_output, rid, sender=_tool_sender(name))

            # DSML 兜底：模型把工具调用写成了文本（已被抑制）且没有结构化工具调用 → 明确报错
            if not saw_tool and any(dsml_saw_block(filters, r) for r in filters):
                yield error_event("模型把工具调用写成了文本（已抑制）。请重试或换种问法", rid)
                return
            yield done(full_response, full_reasoning, rid)
        except Exception as e:
            logger.error("统筹 Agent 异常: %s", e, exc_info=True)
            yield error_event(str(e), rid)
