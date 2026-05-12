import json
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel, Field

from api.v1.models import ChatRequest, SaveMessagesRequest
from yuanai.core.lc import get_llm
from yuanai.core.chat import build_input_messages, stream_agent_events
from yuanai.tools import all_tools
from config.settings import CHAT_TOOLS_ADMIN_SKIP, CHAT_TOOLS_USER_SKIP

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

_SAFE_ERROR = "请求处理失败，请稍后重试"


class MessagesRequest(BaseModel):
    session_id: str = Field(..., min_length=1, description="会话 ID")


def get_chat_tools(role: str = "user"):
    """根据角色获取聊天可用的工具列表"""
    skip = CHAT_TOOLS_ADMIN_SKIP if role == "admin" else CHAT_TOOLS_USER_SKIP
    return [t for t in all_tools if not any(s in t.name for s in skip)]


def _get_db():
    try:
        from db.session import get_db
        return get_db()
    except Exception as e:
        logger.warning("MySQL 连接失败，降级到 SQLite: %s", e)
        from db.session import AgentDatabase
        return AgentDatabase()


def _get_user_id(request: Request) -> int:
    return getattr(request.state, "user_id", None)


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


@router.post("/stream")
async def chat_stream(req: ChatRequest, request: Request, browser_context: bool = Query(False)):
    """SSE 流式聊天"""
    try:
        role = getattr(request.state, "role", "user")
        if browser_context and role == "admin":
            chat_tools = all_tools
        else:
            chat_tools = get_chat_tools(role)

        llm = get_llm(req.model, temperature=req.temperature, verbose=False, streaming=True)

        history = []
        for m in req.history:
            msg_role = m.get("role", "")
            content = m.get("content", "")
            if msg_role == "user":
                history.append(HumanMessage(content=content))
            elif msg_role == "assistant":
                history.append(AIMessage(content=content))

        system_prompt = req.system_prompt
        if any(kw in system_prompt for kw in ["审核", "单题标答"]):
            try:
                from yuanai.rag import get_all_specs
                specs = get_all_specs()
                if specs:
                    system_prompt += f"\n\n---\n# 标注规范（请严格遵守以下规范进行审核判断）\n{specs}"
            except Exception:
                pass

        input_messages = build_input_messages(
            prompt=req.prompt,
            images_base64=req.images,
            history=history,
            system_message=SystemMessage(content=system_prompt),
        )

        async def event_stream():
            try:
                async for event in stream_agent_events(llm, input_messages, chat_tools):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error("SSE 流式聊天异常: %s", e)
                yield f"data: {json.dumps({'type': 'error', 'data': _SAFE_ERROR}, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except Exception as e:
        logger.error("聊天请求初始化失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.post("/session/new")
async def new_session(request: Request):
    """创建新会话"""
    try:
        db = _get_db()
        user_id = _get_user_id(request)
        result = db.create_session(user_id=user_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("创建会话失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.get("/sessions")
async def list_sessions(request: Request):
    """获取会话列表"""
    try:
        db = _get_db()
        user_id = _get_user_id(request)
        return db.get_sessions(user_id=user_id)
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
    """保存对话到数据库"""
    try:
        db = _get_db()
        user_id = _get_user_id(request)
        _verify_session_owner(db, req.session_id, user_id)

        # 批量插入在同一个事务中
        sess = db.Session()
        from db.session import AIChat
        try:
            for msg in req.messages:
                record = AIChat(session_id=req.session_id, role=msg["role"], content=msg["content"])
                sess.add(record)
            if req.title:
                from db.session import ChatSession
                sess.query(ChatSession).filter_by(session_id=req.session_id).update({"title": req.title})
            sess.commit()
            count = len(req.messages)
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
