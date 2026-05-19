import json
import os
import uuid
import base64
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse, FileResponse
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel, Field
from utils.data_path import root_path

from api.v1.models import ChatRequest, SaveMessagesRequest
from yuanai_core.core.lc import get_llm
from yuanai_core.core.chat import build_input_messages, stream_agent_events
from yuanai_core.tools import all_tools

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

_SAFE_ERROR = "请求处理失败，请稍后重试"
_CHAT_IMG_DIR = os.path.join(root_path(), "data", "chat_images")


def _save_chat_image(session_id: str, data_url: str) -> str:
    """将 base64 data URL 保存为文件，返回访问 URL。非 base64 原样返回。"""
    if not data_url.startswith("data:"):
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


@router.get("/image/{session_id}/{filename}")
async def serve_chat_image(session_id: str, filename: str):
    """提供聊天图片"""
    if ".." in session_id or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="非法路径")
    file_path = os.path.join(_CHAT_IMG_DIR, session_id, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path)


class MessagesRequest(BaseModel):
    session_id: str = Field(..., min_length=1, description="会话 ID")




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
async def chat_stream(req: ChatRequest, request: Request):
    """SSE 流式聊天"""
    try:
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

        input_messages = build_input_messages(
            prompt=req.prompt,
            images_base64=req.images,
            history=history,
            system_message=SystemMessage(content=system_prompt),
        )

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
                if msg.get("images"):
                    saved = [_save_chat_image(req.session_id, img) for img in msg["images"]]
                    record.images = json.dumps(saved, ensure_ascii=False)
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
