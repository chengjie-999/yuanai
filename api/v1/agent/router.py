"""Agent WebSocket Hub：管理本地 Agent 连接，中继消息"""

import asyncio
import json
import logging
from typing import Dict

import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])

# agent_id → WebSocket
_agents: Dict[str, WebSocket] = {}

# agent_id → agent info
_agent_info: Dict[str, dict] = {}

# request_id → asyncio.Queue（SSE 桥等待 Agent 回传事件）
_pending: Dict[str, asyncio.Queue] = {}

HEARTBEAT_INTERVAL = 30
HEARTBEAT_TIMEOUT = 90


def _get_agent_status(request: Request, include_activities: bool = False) -> list[dict]:
    """返回 Agent 状态列表（admin 看全部，普通用户只看自己的）"""
    from api.v1.auth.utils import verify_token
    from api.v1.middleware import _extract_token

    token = _extract_token(request)
    payload = verify_token(token) if token else None
    current_user = str(payload.get("user_id", 0)) if payload else "0"
    is_admin = payload.get("role") == "admin" if payload else False

    result = []
    for agent_id in list(_agents.keys()):
        if not is_admin and agent_id != current_user:
            continue
        info = _agent_info.get(agent_id, {})
        entry = {
            "agent_id": agent_id,
            "agent_name": info.get("agent_name", agent_id),
            "capabilities": info.get("capabilities", []),
            "online": True,
            "last_heartbeat": info.get("last_heartbeat", ""),
        }
        if include_activities:
            entry["activities"] = list(reversed(info.get("activities", [])[-10:]))
        result.append(entry)
    return result


@router.get("/status")
async def agent_status(request: Request):
    return _get_agent_status(request)


def get_agent(user_id: int) -> WebSocket | None:
    """查找用户对应的在线 Agent 连接"""
    agent_id = str(user_id)
    ws = _agents.get(agent_id)
    if ws and ws.client_state.name == "CONNECTED":
        return ws
    return None


def get_pending_queue(request_id: str) -> asyncio.Queue:
    """为指定 request_id 获取或创建等待队列"""
    if request_id not in _pending:
        _pending[request_id] = asyncio.Queue()
    return _pending[request_id]


def cleanup_pending(request_id: str):
    """清理已完成请求的队列"""
    _pending.pop(request_id, None)


@router.websocket("/ws/agent/{agent_id}")
async def agent_ws(websocket: WebSocket, agent_id: str):
    # 在 accept 前验证 token
    from api.v1.auth.utils import verify_token
    token = websocket.query_params.get("token", "")
    payload = verify_token(token)
    if not payload:
        await websocket.close(code=4001, reason="token 无效或未提供")
        return
    if str(payload.get("user_id", "")) != agent_id:
        await websocket.close(code=4003, reason="token 与 agent_id 不匹配")
        return

    await websocket.accept()
    _agents[agent_id] = websocket
    logger.info("Agent %s 已连接（当前在线: %d）", agent_id, len(_agents))

    heartbeat_task = asyncio.create_task(_heartbeat(websocket, agent_id))

    try:
        while True:
            raw = await websocket.receive_text()
            event = json.loads(raw)
            event_type = event.get("type", "")
            request_id = event.get("request_id", "")

            if event_type == "hello":
                data = event.get("data", {})
                _agent_info[agent_id] = {
                    "agent_name": data.get("agent_name", agent_id),
                    "capabilities": data.get("capabilities", []),
                    "last_heartbeat": time.strftime("%H:%M:%S"),
                }
                logger.info("Agent %s 注册: %s", agent_id, _agent_info[agent_id])
                continue

            if event_type == "pong":
                if agent_id in _agent_info:
                    _agent_info[agent_id]["last_heartbeat"] = time.strftime("%H:%M:%S")
                continue

            if event_type == "activity":
                # 实时活动状态
                if agent_id in _agent_info:
                    act = event.get("data", {})
                    acts = _agent_info[agent_id].setdefault("activities", [])
                    acts.append({
                        "message": act.get("message", ""),
                        "detail": act.get("detail", ""),
                        "time": time.strftime("%H:%M:%S"),
                    })
                    if len(acts) > 20:
                        acts[:] = acts[-20:]  # 只保留最近 20 条
                continue

            # 把 Agent 事件投递到对应的等待队列（SSE 桥）
            if request_id and request_id in _pending:
                await _pending[request_id].put(event)
            else:
                logger.debug("Agent %s 发送了无等待者的消息: %s", agent_id, event_type)
    except WebSocketDisconnect:
        logger.info("Agent %s 正常断开", agent_id)
    except Exception as e:
        logger.error("Agent %s 连接异常: %s", agent_id, e)
    finally:
        heartbeat_task.cancel()
        # 守卫式清理：仅当注册的仍是当前连接时才移除，避免旧连接断开误删新连接的 socket
        if _agents.get(agent_id) is websocket:
            _agents.pop(agent_id, None)
            _agent_info.pop(agent_id, None)
            # 清理该 agent 关联的所有 pending 请求
            stale = [rid for rid in _pending if rid.startswith(agent_id)]
            for rid in stale:
                cleanup_pending(rid)
            logger.info("Agent %s 已移除（当前在线: %d）", agent_id, len(_agents))


async def _heartbeat(websocket: WebSocket, agent_id: str):
    """定期发送 ping，检测 Agent 是否存活"""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                logger.warning("Agent %s 心跳失败，断开", agent_id)
                await websocket.close()
                break
    except asyncio.CancelledError:
        pass


async def forward_to_agent(user_id: int, chat_request: dict) -> str | None:
    """将对话请求转发给用户对应的 Agent，返回 request_id。Agent 离线返回 None。"""
    ws = get_agent(user_id)
    if ws is None:
        return None

    request_id = chat_request.get("request_id", "")
    if not request_id:
        import uuid
        request_id = str(uuid.uuid4())
        chat_request["request_id"] = request_id

    # 预创建等待队列
    get_pending_queue(request_id)

    try:
        await ws.send_json(chat_request)
        return request_id
    except Exception as e:
        logger.error("向 Agent 转发消息失败: %s", e)
        cleanup_pending(request_id)
        return None
