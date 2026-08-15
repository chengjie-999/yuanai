import json
import os
import uuid
import base64
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse, FileResponse
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field
from utils.data_path import root_path

from api.v1.models import ChatRequest, SaveMessagesRequest
from yuanai_core.core.lc import get_llm
from yuanai_core.core.chat import build_input_messages, stream_agent_events
from yuanai_core.rag import current_user_id
from yuanai_core.tools import all_tools

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

_SAFE_ERROR = "请求处理失败，请稍后重试"
_CHAT_IMG_DIR = os.path.join(root_path(), "data", "chat_images")


def _save_chat_image(session_id: str, data_url: str) -> str:
    """将 base64 data URL 保存为文件，返回访问 URL。非 base64 原样返回。"""
    if not data_url.startswith("data:"):
        return data_url  # 已经是文件 URL，跳过重复保存
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




def _get_db():
    from db.session import get_db
    return get_db()


from api.v1.middleware import get_user_id as _get_user_id


def _verify_session_owner(db, session_id: str, user_id: int):
    """验证会话所有权，不是所有人则抛出 403"""
    sess = db.Session()
    try:
        from db.session import ChatSession
        chat = sess.query(ChatSession).filter_by(session_id=session_id).first()
        if chat and chat.user_id and chat.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权访问该会话")
    finally:
        sess.close()


async def _bridge_sse(queue: asyncio.Queue, request_id: str):
    """Agent 事件队列 → SSE 流（300s 超时按每次事件重置；done/error 终止）"""
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
        pass
    finally:
        cleanup_pending(request_id)


@router.post("/stream")
async def chat_stream(req: ChatRequest, request: Request):
    """SSE 流式聊天（优先走本地 Agent，离线时回退到云端直接调用）"""
    try:
        model = req.model
        # DeepSeek V4 不支持图片 → 自动切到豆包多模态
        if req.images and 'deepseek' in model:
            from config.settings import VISION_MODEL
            model = VISION_MODEL

        history = []
        for m in req.history:
            msg_role = m.get("role", "")
            content = m.get("content", "")
            if msg_role == "user":
                history.append(HumanMessage(content=content))
            elif msg_role == "assistant":
                history.append(AIMessage(content=content))
            elif msg_role == "tool":
                # 工具执行结果消息 — 保留在上下文中让模型知晓历史工具调用
                history.append(ToolMessage(content=content, tool_call_id=m.get("tool_call_id", "")))

        system_prompt = req.system_prompt

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

        # --- 尝试走本地 Agent WebSocket 桥接 ---
        if user_id:
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
            }
            bridged_request_id = await forward_to_agent(user_id, agent_chat_request)

            if bridged_request_id:
                logger.info("chat/stream → Agent 桥接 (user=%s, req=%s)", user_id, bridged_request_id[:8])
                queue = get_pending_queue(bridged_request_id)
                return StreamingResponse(_bridge_sse(queue, bridged_request_id), media_type="text/event-stream")

        # --- 回退：云端直接调用 LLM ---
        logger.info("chat/stream → 云端直接调用 (user=%s, agent offline)", user_id)
        # Agent 离线时没有 delegate 工具，修正系统提示
        offline_prompt = "你是小元AI助手，可以直接使用工具完成任务。可用的工具包括：list_datasets(列出数据集)、preview_dataset(预览)、analyze_dataset(分析)、fetch_url(抓取网页)、parse_html(解析HTML)、get_today_temperature(天气)、calculate_sum(计算)、get_user_memory(用户记忆) 等。直接用工具处理用户请求，简洁回复。任务完成或对话结束时，用表格总结本次完成了什么。"
        input_messages[0]["content"] = offline_prompt
        llm = get_llm(model, temperature=req.temperature, verbose=False, streaming=True)

        async def event_stream():
            try:
                async for event in stream_agent_events(llm, input_messages, all_tools):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error("SSE 流式聊天异常: %s", e)
                yield f"data: {json.dumps({'type': 'error', 'data': _SAFE_ERROR}, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except Exception as e:
        logger.error("聊天请求初始化失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.post("/claude-stream")
async def claude_stream(req: ChatRequest, request: Request):
    """Claude Code 桥接对话：转发给本机 claude 桥接进程（独立 agent_id），离线时回退云端 LLM

    访问控制：仅 admin 或 CLAUDE_BRIDGE_ALLOWED_USERNAMES 白名单用户（防跨用户向他人本机注入）。
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
        for m in req.history:
            if m.get("role") == "user":
                history.append(HumanMessage(content=m.get("content", "")))
            elif m.get("role") == "assistant":
                history.append(AIMessage(content=m.get("content", "")))
            elif m.get("role") == "tool":
                history.append(ToolMessage(content=m.get("content", ""), tool_call_id=m.get("tool_call_id", "")))

        input_messages = build_input_messages(
            prompt=req.prompt,
            images_base64=req.images,
            history=history,
            system_message=SystemMessage(content=req.system_prompt),
        )
        current_user_id.set(user_id if user_id else 0)

        if CLAUDE_BRIDGE_AGENT_ID > 0:
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
                "decision": req.decision,  # 审批决议原样转发（无则 None）
            }
            bridged_request_id = await forward_to_agent(CLAUDE_BRIDGE_AGENT_ID, agent_chat_request)
            if bridged_request_id:
                logger.info("chat/claude-stream → Claude 桥接 (user=%s, session=%s, req=%s)",
                            user_id, req.session_id, bridged_request_id[:8])
                queue = get_pending_queue(bridged_request_id)
                return StreamingResponse(_bridge_sse(queue, bridged_request_id), media_type="text/event-stream")

        # 回退：云端直接调用 LLM
        logger.info("chat/claude-stream → Claude 桥离线，云端回退 (user=%s)", user_id)
        offline_prompt = ("你是小元AI助手（Claude Code 桥接当前离线，已切换云端模式）。"
                          "可以直接使用工具完成任务。简洁回复，任务完成时用表格总结本次完成了什么。")
        input_messages[0]["content"] = offline_prompt
        llm = get_llm(model, temperature=req.temperature, verbose=False, streaming=True)

        async def event_stream():
            try:
                async for event in stream_agent_events(llm, input_messages, all_tools):
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
async def list_sessions(request: Request):
    """获取会话列表（管理员看全部，普通用户只看自己的）"""
    try:
        db = _get_db()
        is_admin = getattr(request.state, "role", "") == "admin"
        user_id = None if is_admin else _get_user_id(request)
        limit = 200 if is_admin else 50
        sessions = db.get_sessions(user_id=user_id, limit=limit)
        # 管理员补充用户名和消息数
        if is_admin:
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
        return {"deleted": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("删除会话失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.post("/messages")
async def get_messages(req: MessagesRequest):
    """获取指定会话的消息"""
    try:
        session_id = req.session_id
        # 先查 Redis 缓存
        from db.cache import get_cached_chat_messages
        cached = get_cached_chat_messages(session_id)
        if cached is not None:
            return cached
        # 缓存未命中，查数据库
        db = _get_db()
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
        from db.session import AIChat
        try:
            # 先删除该会话的全部旧消息，避免重复累积
            sess.query(AIChat).filter_by(session_id=req.session_id).delete()
            count = 0
            for msg in req.messages:
                record = AIChat(session_id=req.session_id, role=msg["role"], content=msg["content"])
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
            if req.title:
                from db.session import ChatSession
                sess.query(ChatSession).filter_by(session_id=req.session_id).update({"title": req.title})
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

        from db.cache import clear_chat_cache
        clear_chat_cache(req.session_id)
        return {"saved": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("保存消息失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)
