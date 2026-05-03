import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from api.v1.models import ChatRequest, SaveMessagesRequest
from yuanai.core.lc import get_llm
from yuanai.core.chat import build_input_messages, stream_agent_events
from yuanai.tools import all_tools

router = APIRouter(prefix="/chat", tags=["chat"])

_CHAT_SKIP = {"browser", "website", "cookie", "scroll", "click", "zoom",
              "restore", "question", "task", "home", "html", "mark_",
              "submit", "confirm", "page_status", "open_", "refresh",
              "launch", "save_cookie", "load_cookie"}
CHAT_TOOLS = [t for t in all_tools if not any(s in t.name for s in _CHAT_SKIP)]


def _get_db():
    from db.session import AgentDatabase
    from utils.sensitive_data import get_mysql_config
    return AgentDatabase(use_mysql=True, mysql_config=get_mysql_config())


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式聊天"""
    try:
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
                async for event in stream_agent_events(llm, input_messages, CHAT_TOOLS):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'data': str(e)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/new")
async def new_session():
    """创建新会话"""
    try:
        db = _get_db()
        result = db.create_session()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_sessions():
    """获取会话列表"""
    try:
        db = _get_db()
        return db.get_sessions()
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
        db = _get_db()
        return db.get_chats(session_id)
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
        return {"saved": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
