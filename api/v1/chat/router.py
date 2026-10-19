import json
import os
import uuid
import base64
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse, FileResponse
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field
from utils.data_path import root_path

from api.v1.models import ChatRequest, SaveMessagesRequest
from yuanai_core.core.lc import get_llm
from yuanai_core.core.chat import build_input_messages, stream_agent_events
from yuanai_core.rag import current_user_id, current_session_id
from yuanai_core.tools import all_tools

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

_SAFE_ERROR = "请求处理失败，请稍后重试"
_CHAT_IMG_DIR = os.path.join(root_path(), "data", "chat_images")

# 云端直连（本地 Agent 离线）专用系统提示——整段重写、去委派化。
# 教训（2026-10-12）：若沿用前端原提示（含「你可以委派的Agent：delegate_to_xxx」），
# 那些工具只存在于本地 Agent 进程，云端回退里不存在——模型会反复发起不存在的
# 工具调用（同一工具名连续多次），且简单任务也先计划委派。
_OFFLINE_SYSTEM_PROMPT = (
    "你是小元AI助手，当前用户的本地智能体离线，由你在云端直接服务。"
    "重要：数据分析/数据采集/自动化等子智能体全部运行在用户本地电脑上，"
    "此时不可用——不要提及「委派」，不要调用任何 delegate 工具，"
    "所有请求都由你自己直接处理，简单任务直接完成，不要计划委派。\n"
    "多步骤组合任务（如「先抓取数据再做统计分析」）：用 create_plan 工具"
    "把任务拆成 1-8 步草稿计划（每步写清 skill 和意图，信息不足先问用户），"
    "建好后向用户复述步骤并说明「说『执行』才会开始」；用户明确说执行时"
    "再调用 execute_plan。不要用文字代替计划，不要自行开始执行。\n"
    "可直接使用的工具：create_plan(制定计划)、execute_plan(执行计划)、"
    "get_plan_status(查计划进度)、list_datasets(列出数据集)、"
    "preview_dataset(预览数据集)、analyze_dataset(分析数据)、"
    "search_web(联网搜索，query 用核心短语分词；摘要通常已足够回答，不必逐条抓取)、fetch_url(抓取网页)、parse_html(解析HTML)、get_today_temperature(天气)、"
    "calculate_sum(计算)、get_user_memory(读取用户记忆)、"
    "remember_user_info(记住用户信息)、organize_user_memory(整理记忆)、"
    "retrieve_planet_knowledge(检索知识星球)、search_pubmed(PubMed 文献检索)、"
    "get_species_info(物种导航) 等。\n"
    "群聊说话人协议：历史消息中带【xx Agent】前缀或其他智能体身份的内容不是你说的，"
    "不要复述、冒充或替其他智能体总结。\n"
    "工作原则：直接用工具处理用户请求，简洁回复；工具不可用时直接说明原因；"
    "任务完成或对话结束时，用表格总结本次完成了什么。"
)

# 能力边界身份卡（docs/agents/cloud_fallback.md，单一事实源）：
# 云端回退智能体知道自己没有委派/脚本能力，不去发起注定失败的工具调用
try:
    from yuanai_core.agent_docs import agent_doc as _agent_doc
    _CC = _agent_doc("cloud_fallback")
    if _CC:
        _OFFLINE_SYSTEM_PROMPT += "\n\n" + _CC
except Exception:
    pass


def _save_chat_image(session_id: str, data_url: str) -> str:
    """将 base64 data URL 保存为文件，返回访问 URL。非 base64 原样返回。"""
    if not data_url.startswith("data:"):
        return data_url  # 已经是文件 URL，跳过重复保存
    # 路径穿越防护（2026-10-19）：session_id 必须是 UUID 形态，否则不落盘
    if not re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}", session_id or ""):
        return data_url
    try:
        header, b64 = data_url.split(",", 1)
        ext = "png"
        if "image/jpeg" in header:
            ext = "jpg"
        elif "image/png" in header:
            ext = "png"
        elif "image/gif" in header:
            ext = "gif"
        elif "image/webp" in header:
            ext = "webp"
        img_bytes = base64.b64decode(b64)
        sid_dir = os.path.join(_CHAT_IMG_DIR, session_id)
        os.makedirs(sid_dir, exist_ok=True)
        fname = f"{uuid.uuid4().hex[:12]}.{ext}"
        fpath = os.path.join(sid_dir, fname)
        with open(fpath, "wb") as f:
            f.write(img_bytes)
        return f"/api/v1/chat/image/{session_id}/{fname}"
    except Exception:
        logger.warning("聊天图片保存失败", exc_info=True)
        return data_url


@router.post("/main-session")
async def ensure_main_session(request: Request):
    """取/建当前用户的置顶主对话（豆包式；每用户一条）"""
    user_id = _get_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    return _get_db().ensure_main_session(user_id)


@router.get("/image/{session_id}/{filename}")
async def serve_chat_image(session_id: str, filename: str):
    """提供聊天图片（文件名含 UUID 永久有效，缓存 1 年）"""
    base_dir = os.path.realpath(_CHAT_IMG_DIR)
    file_path = os.path.normpath(os.path.join(base_dir, session_id, filename))
    if not file_path.startswith(base_dir + os.sep) or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path, headers={
        "Cache-Control": "private, max-age=31536000, immutable",
    })


class MessagesRequest(BaseModel):
    session_id: str = Field(..., min_length=1, description="会话 ID")


class FeedbackRequest(BaseModel):
    session_id: str = Field(..., min_length=1, description="会话 ID")
    message_index: int = Field(..., ge=0, description="消息下标（0 起，与前端数组一致）")
    liked: Optional[bool] = Field(None, description="点赞（true=赞，false=取消；与 disliked 互斥）")
    disliked: Optional[bool] = Field(None, description="点踩（true=踩，false=取消；与 liked 互斥）")




from api.v1.db_helpers import get_db as _get_db, verify_session_owner as _verify_session_owner
from api.v1.middleware import get_user_id as _get_user_id


async def _bridge_sse(queue: asyncio.Queue, request_id: str, user_id: int = 0):
    """Agent 事件队列 → SSE 流（300s 超时按每次事件重置；done/error 终止）
    B1-12：客户端中断（停止生成/关页）→ 通知本地 Agent 终止脚本子进程"""
    from api.v1.agent.router import cleanup_pending
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=300)
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'error', 'data': 'Agent 响应超时'}, ensure_ascii=False)}\n\n"
                break

            if event.get("type") in ("done", "error"):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                break

            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    except asyncio.CancelledError:
        # B1-12 停止联动：SSE 被 abort（停止生成）→ 通知 Agent 杀脚本子进程
        try:
            from api.v1.agent.router import send_stop_to_agent
            asyncio.create_task(send_stop_to_agent(user_id, request_id))
        except Exception:
            logger.warning("停止通知发送失败（不影响主流程）", exc_info=True)
    finally:
        cleanup_pending(request_id)


# 信封四字段（视图滤波在 views.py；此处保证扁平化时不丢身份）
_ENVELOPE_KEEP = ("sender", "recipient", "turn", "type")
_ENVELOPE_DEFAULTS = {"sender": "", "recipient": "", "turn": 0, "type": "chat"}


def _env_of(m: dict) -> dict:
    """消息的信封字段子集（等于默认值不保留，payload 更小）"""
    return {k: m[k] for k in _ENVELOPE_KEEP
            if k in m and m[k] != _ENVELOPE_DEFAULTS[k]}


def _fix_history_for_api(history: list) -> list:
    """清洗历史：工具调用结构（tool_calls/tool）统一扁平化为普通文本。

    云端 API 对 tool 消息有严格配对校验（400: 'Messages with role tool must be a
    response to a preceding message with tool_calls'），而历史里的工具上下文用文本
    表达已足够让模型理解，故全部转为文本，彻底规避结构校验问题。
    信封字段（sender/recipient/turn/type）在扁平化时透传。
    """
    fixed = []
    for m in history:
        role = m.get("role", "")
        if role == "tool":
            fixed.append({"role": "user", "content": f"[工具结果] {str(m.get('content', ''))[:2000]}",
                          **_env_of(m)})
        elif role == "assistant" and m.get("tool_calls"):
            fixed.append({"role": "assistant", "content": m.get("content", ""),
                          **_env_of(m)})
        else:
            fixed.append(m)
    return fixed


def _langchain_from_items(items: list, prompt: str, images, system_content: str) -> list:
    """items（信封视图输出：role/content/tool_calls）→ langchain input_messages"""
    history = []
    for v in items:
        role = v.get("role", "")
        if role == "user":
            history.append(HumanMessage(content=v.get("content", "")))
        elif role == "assistant":
            history.append(AIMessage(content=v.get("content", "")))
        elif role == "tool":
            history.append(ToolMessage(content=v.get("content", ""),
                                       tool_call_id=v.get("tool_call_id", "")))
    return build_input_messages(prompt=prompt, images_base64=images,
                                history=history,
                                system_message=SystemMessage(content=system_content))


@router.post("/stream")
async def chat_stream(req: ChatRequest, request: Request):
    """SSE 流式聊天（优先走本地 Agent，离线时回退到云端直接调用）"""
    try:
        # 每日消息配额（成本护栏）：admin 不限，user 超限拒绝；Redis 不可用时宽松放行
        user_id = _get_user_id(request)
        from config.settings import DAILY_MESSAGE_QUOTA
        if DAILY_MESSAGE_QUOTA > 0 and getattr(request.state, "role", "") != "admin":
            from datetime import datetime
            from api.v1.db_helpers import check_daily_quota
            if not check_daily_quota(f"msg:{user_id}", DAILY_MESSAGE_QUOTA):
                raise HTTPException(status_code=429, detail=f"今日消息额度已用完（{DAILY_MESSAGE_QUOTA} 条/天），请明天再来")

        model = req.model
        # 图片识别（2026-10-16 收窄）：DeepSeek V4.1 Flash 原生支持图像输入，
        # 豆包全系多模态——只有不支持图片的 deepseek-v4-pro 才切豆包（切换有延迟）
        if req.images and model == "deepseek-v4-pro":
            from config.settings import VISION_MODEL
            model = VISION_MODEL

        target = getattr(req, "target_agent", "") or ""

        history = []
        # 信封数组：与 history 锁步构建（system 首项 + 截断说明 + 历史各项 + 末位 prompt 项），
        # 再随 payload 传给本地 Agent（build_input_messages 会重建 dict 丢附加键，
        # 信封必须走并行数组——message.py 协议）
        envelopes = [{}]  # index 0 = system
        # 上下文护栏：历史只保留最近 60 条——更早的对话已由记忆机制折叠进
        # 长期记忆（system prompt 已注入），避免主对话无限增长打爆上下文。
        # 小窗会话（持久定向子智能体，如 @自动化）放宽到 200 条：长任务对话
        # 不被主对话口径切断（@Claude 走 claude-stream 天然不截断）
        hist_limit = 200 if target else 60
        raw_history = req.history[-hist_limit:] if len(req.history) > hist_limit else req.history
        truncated = len(req.history) > hist_limit
        if truncated:
            # P4 归档提示：被整理的历史按说话人计数（群聊里各智能体的段落去向可见）
            from collections import Counter
            dropped = req.history[:-hist_limit]
            cnt = Counter(str(m.get("sender") or m.get("role")) for m in dropped)
            parts = []
            for s, n in cnt.most_common(3):
                label = {"claude": "Claude Code", "automation": "自动化",
                         "orchestrator": "小元AI", "user": "你"}.get(s, s)
                parts.append(f"{label} {n} 条")
            note = (f"（更早的对话已整理进长期记忆"
                    f"{'；被整理：' + '、'.join(parts) if parts else ''}，见上方用户信息）")
            history.append(HumanMessage(content=note))
            envelopes.append({})
        turn = 0
        for m in _fix_history_for_api(raw_history):
            msg_role = m.get("role", "")
            content = m.get("content", "")
            if msg_role == "user":
                history.append(HumanMessage(content=content))
                turn += 1
            elif msg_role == "assistant":
                history.append(AIMessage(content=content))
            elif msg_role == "tool":
                # 工具执行结果消息 — 保留在上下文中让模型知晓历史工具调用
                history.append(ToolMessage(content=content, tool_call_id=m.get("tool_call_id", "")))
            envelopes.append(_env_of(m))
        # 末位 prompt 项信封（新用户消息：sender=user，定向 target，轮次=历史 user 数+1）
        envelopes.append({"sender": "user", "recipient": target,
                          "turn": turn + 1, "type": "chat"})

        system_prompt = req.system_prompt
        # 注意（2026-10-17）：桥接路径不在此注入自报——本地统筹用自己的
        # orch_model（AGENT_MODEL_MAP）注入，此处用 req.model 会造成两条互斥
        # 的「你实际运行的模型 ID」；自报注入只在云端回退分支做

        # 获取当前用户 ID
        user_id = _get_user_id(request)

        # 注入用户记忆到 system prompt
        if user_id:
            from db.session import get_db
            memory = get_db().get_user_memory(user_id)
            if memory:
                system_prompt = f"关于当前用户的已知信息（请用它来个性化回复）：\n{memory}\n\n{system_prompt}"

        input_messages = build_input_messages(
            prompt=req.prompt,
            images_base64=req.images,
            history=history,
            system_message=SystemMessage(content=system_prompt),
        )

        # 设置当前用户上下文，知识库检索时自动过滤私有/共享
        current_user_id.set(user_id if user_id else 0)
        current_session_id.set(getattr(req, "session_id", "") or "")

        # --- 尝试走本地 Agent WebSocket 桥接（云端模式 force_cloud 时跳过） ---
        if user_id and not req.force_cloud:
            from api.v1.agent.router import forward_to_agent, get_pending_queue, cleanup_pending
            import uuid as _uuid

            agent_request_id = str(_uuid.uuid4())
            agent_chat_request = {
                "type": "chat_request",
                "request_id": agent_request_id,
                "session_id": getattr(req, "session_id", ""),
                "user_id": user_id,
                "messages": input_messages,
                "images": req.images,
                # 聊天框推理强度开关（low/high）透传本地 Agent
                "reasoning_effort": req.reasoning_effort if req.reasoning_effort in ("low", "medium", "high") else "low",
                # @指定智能体（群聊式定向委派；空=统筹自行路由）
                "target_agent": target,
                # 消息信封（与 messages 等长，本地 Agent 视图滤波用）
                "envelopes": envelopes,
            }
            bridged_request_id = await forward_to_agent(user_id, agent_chat_request)

            if bridged_request_id:
                logger.info("chat/stream → Agent 桥接 (user=%s, req=%s)", user_id, bridged_request_id[:8])
                queue = get_pending_queue(bridged_request_id)
                return StreamingResponse(_bridge_sse(queue, bridged_request_id, user_id), media_type="text/event-stream")

        # --- 回退：云端直接调用 LLM ---
        logger.info("chat/stream → 云端直接调用 (user=%s, agent offline)", user_id)
        # 视图滤波：云端直连（或 Agent 离线回退）按 viewer 身份裁剪历史
        # （信封全空时 view_for 退化为直通 = 旧行为）
        from yuanai_core.core.views import view_for
        viewer = target or "orchestrator"
        fixed_items = _fix_history_for_api(raw_history)
        fixed_envs = envelopes[1 + (1 if truncated else 0):-1]
        view = view_for(viewer, fixed_items, envelopes=fixed_envs)
        input_messages = _langchain_from_items(view, req.prompt, req.images, system_prompt)

        # 离线系统提示（2026-10-12 根治「重复工具调用 + 简单任务也打算委派」）：
        # 前端原提示含「你可以委派的Agent：delegate_to_xxx」段——那些工具只存在于
        # 本地 Agent 进程，云端回退里不存在，模型反复发起不存在的工具调用（同一个
        # 工具名连续多次）。云端直连必须整段重写去委派化，不再拼接原提示。
        # 记忆注入：用户记忆已注入 system_prompt，这里重写会丢——重新注入。
        from yuanai_core.core.chat import limited_tools
        offline_prompt = _OFFLINE_SYSTEM_PROMPT
        if user_id:
            from db.session import get_db as _db
            try:
                mem = _db().get_user_memory(user_id)
                if mem:
                    offline_prompt = f"关于当前用户的已知信息（请用它来个性化回复）：\n{mem}\n\n{offline_prompt}"
            except Exception:
                pass
        if target and target in ("analysis", "collection", "automation", "claude"):
            role_hint = {"analysis": "数据分析", "collection": "数据采集",
                         "automation": "自动化", "claude": "Claude Code"}[target]
            offline_prompt += (f"\n本轮用户 @{role_hint} 指定由「{role_hint}智能体」回答："
                               f"从此刻起你就是{role_hint}智能体本人，直接以该身份与口吻回答，"
                               f"不要自称小元AI或统筹助手，不要提及委派过程或身份切换。")
        # 模型如实自报（2026-10-16 起，2026-10-17 归一化+模板化）：
        # 模板来自后台设定中心 self_report_template（模型 ID 运行时真值填充）
        from yuanai_core.core.lc import resolve_model_id
        from config.settings import self_report_text
        offline_prompt += "\n\n" + self_report_text(resolve_model_id(model))
        input_messages[0]["content"] = offline_prompt
        effort = req.reasoning_effort if req.reasoning_effort in ("low", "medium", "high") else "low"
        llm = get_llm(model, temperature=req.temperature, verbose=False, streaming=True,
                      reasoning_effort=effort)

        async def event_stream():
            try:
                # 同名工具单轮最多调 3 次（防重复调用死循环）+ LangGraph 轮数上限
                async for event in stream_agent_events(llm, input_messages, limited_tools(all_tools)):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as e:
                # exc_info：异常来自哪一行一眼可见（曾出现「string indices must be integers」
                # 无法定位——只打 str(e) 丢了堆栈）
                logger.error("SSE 流式聊天异常: %s", e, exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'data': _SAFE_ERROR}, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except Exception as e:
        logger.error("聊天请求初始化失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.post("/claude-stream")
async def claude_stream(req: ChatRequest, request: Request):
    """Claude Code 桥接对话：转发给该用户本机的 Agent（mode=claude 分支），离线时回退云端 LLM

    路由：CLAUDE_BRIDGE_AGENT_ID > 0 时走共享桥接（固定 agent_id，多用户共用一台本机）；
    否则转发给 agent_id == 当前用户 user_id 的 Agent（每用户一台本机，多 PC 天然扩展）。
    访问控制：仅 admin 或 CLAUDE_BRIDGE_ALLOWED_USERNAMES 白名单用户。
    """
    from config.settings import CLAUDE_BRIDGE_AGENT_ID, CLAUDE_BRIDGE_ALLOWED_USERNAMES

    # 访问控制
    role = getattr(request.state, "role", "")
    username = getattr(request.state, "username", "")
    if role != "admin" and username not in CLAUDE_BRIDGE_ALLOWED_USERNAMES:
        raise HTTPException(status_code=403, detail="无权访问 Claude Code 桥接")

    try:
        user_id = _get_user_id(request)
        model = req.model

        # DeepSeek 不支持图片 → 自动切豆包多模态
        if req.images and "deepseek" in model:
            from config.settings import VISION_MODEL
            model = VISION_MODEL

        history = []
        envelopes = [{}]  # 与 /stream 同构：system 首项 + 历史 + 末位 prompt 项
        fixed_items = _fix_history_for_api(req.history)
        turn = 0
        for m in fixed_items:
            if m.get("role") == "user":
                history.append(HumanMessage(content=m.get("content", "")))
                turn += 1
            elif m.get("role") == "assistant":
                history.append(AIMessage(content=m.get("content", "")))
            elif m.get("role") == "tool":
                history.append(ToolMessage(content=m.get("content", ""), tool_call_id=m.get("tool_call_id", "")))
            envelopes.append(_env_of(m))
        envelopes.append({"sender": "user", "recipient": "claude",
                          "turn": turn + 1, "type": "chat"})

        input_messages = build_input_messages(
            prompt=req.prompt,
            images_base64=req.images,
            history=history,
            system_message=SystemMessage(content=req.system_prompt),
        )
        current_user_id.set(user_id if user_id else 0)
        current_session_id.set(getattr(req, "session_id", "") or "")

        # 目标 agent：共享桥接（固定 id）或该用户自己的本机 Agent
        target_agent_id = CLAUDE_BRIDGE_AGENT_ID if CLAUDE_BRIDGE_AGENT_ID > 0 else user_id

        if target_agent_id:
            from api.v1.agent.router import forward_to_agent, get_pending_queue
            import uuid as _uuid

            agent_request_id = str(_uuid.uuid4())
            agent_chat_request = {
                "type": "chat_request",
                "request_id": agent_request_id,
                "session_id": req.session_id,
                "user_id": user_id,
                "messages": input_messages,
                "images": req.images,
                "mode": "claude",  # 本机 Agent 的 claude 分支
                "decision": req.decision,  # 审批决议原样转发（无则 None）
                "envelopes": envelopes,
            }
            bridged_request_id = await forward_to_agent(target_agent_id, agent_chat_request)
            if bridged_request_id:
                logger.info("chat/claude-stream → Claude 桥接 (target=%s, user=%s, session=%s, req=%s)",
                            target_agent_id, user_id, req.session_id, bridged_request_id[:8])
                queue = get_pending_queue(bridged_request_id)
                return StreamingResponse(_bridge_sse(queue, bridged_request_id, target_agent_id), media_type="text/event-stream")

        # 回退：云端直接调用 LLM
        logger.info("chat/claude-stream → Claude 桥离线，云端回退 (user=%s)", user_id)
        # 视图滤波：以 Claude 身份裁剪历史（信封全空退化为直通）
        from yuanai_core.core.views import view_for
        view = view_for("claude", fixed_items, envelopes=envelopes[1:-1])
        input_messages = _langchain_from_items(view, req.prompt, req.images, req.system_prompt)
        offline_prompt = ("你是小元AI助手（Claude Code 桥接当前离线，已切换云端模式）。"
                          "不要提及「委派」、不要调用任何 delegate 工具——子智能体在本机"
                          "Agent 上且当前离线，所有请求由你自己直接处理。"
                          "可以直接使用工具完成任务。简洁回复，任务完成时用表格总结本次完成了什么。")
        # 模型如实自报（2026-10-17 补齐：claude-stream 回退此前漏注入）
        from yuanai_core.core.lc import resolve_model_id
        from config.settings import self_report_text
        offline_prompt += "\n\n" + self_report_text(resolve_model_id(model))
        input_messages[0]["content"] = offline_prompt
        llm = get_llm(model, temperature=req.temperature, verbose=False, streaming=True)

        async def event_stream():
            try:
                from yuanai_core.core.chat import limited_tools
                async for event in stream_agent_events(llm, input_messages, limited_tools(all_tools)):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error("claude-stream 云端回退异常: %s", e)
                yield f"data: {json.dumps({'type': 'error', 'data': _SAFE_ERROR}, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("claude-stream 请求初始化失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.get("/system-prompt")
async def get_system_prompt(request: Request):
    """助手设定（登录可见）：前端取回提示词——chat_system_prompt 为空时前端
    用内置默认；self_report_template 仅后台可改，模型 ID 运行时真值填充"""
    from config.settings import CHAT_SYSTEM_PROMPT, SELF_REPORT_TEMPLATE, CAPABILITY_NOTE
    return {
        "system_prompt": CHAT_SYSTEM_PROMPT,
        "self_report_template": SELF_REPORT_TEMPLATE,
        "capability_note": CAPABILITY_NOTE,
    }


class NewSessionRequest(BaseModel):
    title: str = Field("新对话", description="会话标题")


@router.post("/session/new")
async def new_session(req: NewSessionRequest, request: Request):
    """创建新会话"""
    try:
        db = _get_db()
        user_id = _get_user_id(request)
        result = db.create_session(title=req.title, user_id=user_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("创建会话失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.get("/sessions")
async def list_sessions(request: Request, own: bool = False):
    """获取会话列表（管理员看全部，普通用户只看自己的）
    own=1（聊天侧栏专用）：一律只看当前用户的——否则 admin 侧栏会把
    其他用户的主对话也带📌显示（每用户一条主对话 → 侧栏出现多个置顶）。"""
    try:
        db = _get_db()
        is_admin = getattr(request.state, "role", "") == "admin"
        if own:
            user_id = _get_user_id(request)
            limit = 50
        else:
            user_id = None if is_admin else _get_user_id(request)
            limit = 200 if is_admin else 50
        sessions = db.get_sessions(user_id=user_id, limit=limit)
        # 管理员补充用户名和消息数（侧栏 own=1 无需补充）
        if is_admin and not own:
            from db.session import User, ChatSession, AIChat
            from sqlalchemy import func
            sess = db.Session()
            try:
                sids = [s["session_id"] for s in sessions]
                # 消息数
                msg_counts = dict(
                    sess.query(AIChat.session_id, func.count(AIChat.id))
                    .filter(AIChat.session_id.in_(sids))
                    .group_by(AIChat.session_id).all()
                )
                # user_id 映射
                uid_map = dict(
                    sess.query(ChatSession.session_id, ChatSession.user_id)
                    .filter(ChatSession.session_id.in_(sids)).all()
                )
                uids = list(set(uid_map.values()))
                user_map = {}
                if uids:
                    user_map = dict(
                        sess.query(User.id, User.username)
                        .filter(User.id.in_(uids)).all()
                    )
                for s in sessions:
                    s["message_count"] = msg_counts.get(s["session_id"], 0)
                    uid = uid_map.get(s["session_id"])
                    s["username"] = user_map.get(uid, "-") if uid else "-"
            finally:
                sess.close()
        return sessions
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取会话列表失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.delete("/session/{session_id}")
async def delete_session(session_id: str, request: Request):
    """删除会话"""
    try:
        db = _get_db()
        user_id = _get_user_id(request)
        _verify_session_owner(db, session_id, user_id)
        db.delete_session(session_id)
        # 清除消息缓存（2026-10-19：此前 TTL 内仍可读已删除对话）
        from db.cache import clear_chat_cache
        clear_chat_cache(session_id)
        return {"deleted": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("删除会话失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.post("/messages")
async def get_messages(req: MessagesRequest, request: Request):
    """获取指定会话的消息"""
    try:
        session_id = req.session_id
        # 会话归属校验（2026-10-19 安全收口：此前已知 session_id 即可读他人对话）
        db = _get_db()
        user_id = _get_user_id(request)
        _verify_session_owner(db, session_id, user_id)
        # 先查 Redis 缓存
        from db.cache import get_cached_chat_messages
        cached = get_cached_chat_messages(session_id)
        if cached is not None:
            return cached
        # 缓存未命中，查数据库
        messages = db.get_chats(session_id)
        # 写入缓存（包括空列表，避免反复查库）
        from db.cache import cache_chat_messages
        cache_chat_messages(session_id, messages)
        return messages
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取消息失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.post("/save")
async def save_messages(req: SaveMessagesRequest, request: Request):
    """保存对话到数据库（先删旧记录，再批量插入，避免重复）"""
    try:
        db = _get_db()
        user_id = _get_user_id(request)
        _verify_session_owner(db, req.session_id, user_id)

        sess = db.Session()
        from db.session import AIChat, AIChatFeedback
        try:
            # 先删除该会话的全部旧消息，避免重复累积
            sess.query(AIChat).filter_by(session_id=req.session_id).delete()
            # 同步清理孤儿点赞：消息被截断后，下标超出新消息范围的反馈行一并删除
            sess.query(AIChatFeedback).filter(
                AIChatFeedback.session_id == req.session_id,
                AIChatFeedback.message_index >= len(req.messages),
            ).delete(synchronize_session=False)
            # 信封落列：turn 兜底补齐（旧客户端无信封时按 user 计数推导）
            from yuanai_core.core.message import assign_turns
            assign_turns(req.messages)
            count = 0
            for msg in req.messages:
                record = AIChat(
                    session_id=req.session_id, role=msg["role"], content=msg["content"],
                    sender=msg.get("sender") or ("user" if msg["role"] == "user" else "orchestrator"),
                    recipient=msg.get("recipient") or "",
                    turn=msg.get("turn") or 0,
                    type=msg.get("type") or "chat",
                )
                if msg.get("images"):
                    # data: URL 是新的需要保存；/api/v1/chat/image/ 是已保存的跳过
                    saved = []
                    for img in msg["images"]:
                        if isinstance(img, str) and img.startswith("/api/v1/"):
                            saved.append(img)  # 已经是文件 URL
                        else:
                            saved.append(_save_chat_image(req.session_id, img))
                    record.images = json.dumps(saved, ensure_ascii=False)
                sess.add(record)
                count += 1
            # 更新会话：标题按需、update_time 每次必刷（会话列表按最后活跃排序依赖此字段）
            from db.session import ChatSession
            from sqlalchemy.sql import func
            chat_update = {"update_time": func.now()}
            # C AI 会话标题：仅当现标题仍是自动标题（空/新对话/首条截断）才覆盖，
            # AI 已生成的标题不被后续消息的自动标题压掉
            if req.title:
                from api.v1.chat.title_gen import _is_auto_title
                from yuanai_core.core.message import text_of
                cur = sess.query(ChatSession).filter_by(session_id=req.session_id).first()
                first_user = ""
                for m in req.messages or []:
                    if m.get("role") == "user":
                        first_user = text_of(m.get("content")).strip()
                        break
                if cur and _is_auto_title(cur.title, first_user):
                    chat_update["title"] = req.title
            sess.query(ChatSession).filter_by(session_id=req.session_id).update(chat_update)
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

        from db.cache import clear_chat_cache
        clear_chat_cache(req.session_id)

        # 记忆折叠触发（fire-and-forget）：超阈值才真正入队；任何异常不影响保存
        try:
            from api.v1.chat.memory_fold import maybe_schedule_memory_fold
            maybe_schedule_memory_fold(
                req.session_id, user_id, len(req.messages),
                sum(len(m.get("content") or "") for m in req.messages),
            )
        except Exception:
            logger.warning("记忆压缩调度失败（不影响保存）", exc_info=True)

        # 会话标题 AI 生成（fire-and-forget）：仅当标题仍是自动标题时触发一次
        try:
            from api.v1.chat.title_gen import maybe_generate_title
            maybe_generate_title(req.session_id, req.messages)
        except Exception:
            logger.warning("标题生成调度失败（不影响保存）", exc_info=True)

        return {"saved": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("保存消息失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.post("/feedback")
async def set_message_feedback(req: FeedbackRequest, request: Request):
    """点赞/点踩一条 AI 消息（按会话内消息下标定位；liked/disliked 三态互斥）

    服务端归一：liked=True → 赞 1 踩 0；disliked=True → 赞 0 踩 1；
    其余（含两者皆 false/None）→ 两态皆 0（取消）。
    旧客户端只发 liked 的行为完全不变。
    """
    try:
        db = _get_db()
        user_id = _get_user_id(request)
        _verify_session_owner(db, req.session_id, user_id)

        liked = 1 if req.liked is True else 0
        disliked = 1 if (req.disliked is True and not liked) else 0

        from db.session import AIChatFeedback
        sess = db.Session()
        try:
            row = sess.query(AIChatFeedback).filter_by(
                session_id=req.session_id, message_index=req.message_index,
            ).first()
            if row:
                row.liked = liked
                row.disliked = disliked
                row.user_id = user_id
            else:
                sess.add(AIChatFeedback(
                    session_id=req.session_id,
                    message_index=req.message_index,
                    liked=liked,
                    disliked=disliked,
                    user_id=user_id,
                ))
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()
        return {"ok": True, "liked": bool(liked), "disliked": bool(disliked)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("保存消息反馈失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.get("/feedback")
async def get_message_feedback(request: Request, session_id: str = Query(..., min_length=1, description="会话 ID")):
    """获取会话内所有消息的反馈状态，返回 {消息下标: {liked, disliked}}（两态皆 0 的不返回）"""
    try:
        db = _get_db()
        user_id = _get_user_id(request)
        _verify_session_owner(db, session_id, user_id)

        from db.session import AIChatFeedback
        sess = db.Session()
        try:
            rows = sess.query(AIChatFeedback).filter_by(session_id=session_id).all()
            return {str(r.message_index): {"liked": bool(r.liked), "disliked": bool(r.disliked)}
                    for r in rows if r.liked or r.disliked}
        finally:
            sess.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取消息反馈失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)
