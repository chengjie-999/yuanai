import json
import asyncio
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from api.v1.models import ChatRequest, SaveMessagesRequest
from yuanai.core.lc import get_llm
from yuanai.core.chat import build_input_messages, stream_agent_events
from yuanai.tools import all_tools
from config.settings import CHAT_TOOLS_ADMIN_SKIP, CHAT_TOOLS_USER_SKIP

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_tools(role: str = "user"):
    """根据角色获取聊天可用的工具列表"""
    skip = CHAT_TOOLS_ADMIN_SKIP if role == "admin" else CHAT_TOOLS_USER_SKIP
    return [t for t in all_tools if not any(s in t.name for s in skip)]


def _get_db():
    try:
        from db.session import get_db
        return get_db()
    except Exception as e:
        print(f"⚠️ MySQL 连接失败: {e}")
        from db.session import AgentDatabase
        return AgentDatabase()


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
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "user":
                history.append(HumanMessage(content=content))
            elif role == "assistant":
                history.append(AIMessage(content=content))

        input_messages = build_input_messages(
            prompt=req.prompt,
            images_base64=req.images,
            history=history,
            system_message=SystemMessage(content=req.system_prompt),
        )

        async def event_stream():
            try:
                async for event in stream_agent_events(llm, input_messages, chat_tools):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'data': str(e)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/new")
async def new_session(request: Request):
    """创建新会话"""
    try:
        db = _get_db()
        user_id = getattr(request.state, "user_id", None)
        result = db.create_session(user_id=user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_sessions(request: Request):
    """获取会话列表"""
    try:
        db = _get_db()
        user_id = getattr(request.state, "user_id", None)
        return db.get_sessions(user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    try:
        db = _get_db()
        db.delete_session(session_id)
        return {"deleted": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/messages")
async def get_messages(req: dict):
    """获取指定会话的消息"""
    try:
        session_id = req.get("session_id", "")
        if not session_id:
            return []
        # 先查 Redis 缓存
        from db.cache import get_cached_chat_messages
        cached = get_cached_chat_messages(session_id)
        if cached is not None:
            return cached
        # 缓存未命中，查数据库
        db = _get_db()
        messages = db.get_chats(session_id)
        # 写入缓存
        if messages:
            from db.cache import cache_chat_messages
            cache_chat_messages(session_id, messages)
        return messages
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save")
async def save_messages(req: SaveMessagesRequest):
    """保存对话到数据库"""
    try:
        db = _get_db()
        count = 0
        for msg in req.messages:
            db.add_chat(req.session_id, msg["role"], msg["content"])
            count += 1
        # 清除 Redis 缓存（下次读取时重新缓存）
        from db.cache import clear_chat_cache
        clear_chat_cache(req.session_id)
        # 如果传了标题，更新会话标题
        if req.title:
            from db.session import ChatSession
            sess = db.Session()
            try:
                sess.query(ChatSession).filter_by(session_id=req.session_id).update({"title": req.title})
                sess.commit()
            finally:
                sess.close()
        return {"saved": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
