"""Agent WebSocket Hub：管理本地 Agent 连接，中继消息"""

import asyncio
import json
import logging
import secrets
from datetime import datetime
from typing import Dict

import time
from pydantic import BaseModel
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, HTTPException

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

    # 普通用户可见范围：旧模式直连（agent_id==user_id）+ 一对一绑定的设备
    allowed_ids = {current_user}
    if payload and not is_admin:
        bound = _get_bound_agent_id(int(payload["user_id"]))
        if bound:
            allowed_ids.add(bound)

    result = []
    for agent_id in list(_agents.keys()):
        if not is_admin and agent_id not in allowed_ids:
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

    # Claude Code 桥接进程对白名单用户可见（前端据此给「⌘ Claude Code」按钮置灰/点亮）
    from config.settings import CLAUDE_BRIDGE_AGENT_ID, CLAUDE_BRIDGE_ALLOWED_USERNAMES
    bridge_id = str(CLAUDE_BRIDGE_AGENT_ID)
    # 跳过主循环已包含的情况（桥接用户本人 / admin 看全部），避免重复条目
    if CLAUDE_BRIDGE_AGENT_ID and bridge_id in _agents and not any(e["agent_id"] == bridge_id for e in result):
        username = payload.get("username", "") if payload else ""
        if is_admin or (username and username in CLAUDE_BRIDGE_ALLOWED_USERNAMES):
            info = _agent_info.get(bridge_id, {})
            entry = {
                "agent_id": bridge_id,
                "agent_name": info.get("agent_name", "Claude Code 桥接"),
                "capabilities": info.get("capabilities", ["claude_code"]),
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


class AgentRegisterRequest(BaseModel):
    install_code: str
    machine_name: str = ""


@router.post("/register")
async def register_agent(req: AgentRegisterRequest):
    """本机 Agent 安装注册：消费后台签发的安装码，返回 agent_id + agent_secret（公开路径，安装码即凭证）"""
    code = req.install_code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="安装码不能为空")
    try:
        from db.session import get_db, AgentDevice
        db = get_db()
        sess = db.Session()
        try:
            dev = sess.query(AgentDevice).filter_by(install_code=code).first()
            if not dev:
                raise HTTPException(status_code=404, detail="安装码不存在")
            if dev.agent_secret:
                raise HTTPException(status_code=400, detail="该安装码已被注册使用")
            dev.agent_secret = secrets.token_hex(32)
            dev.machine_name = (req.machine_name or "")[:64]
            dev.last_seen = datetime.utcnow()
            sess.commit()
            logger.info("Agent 设备注册: id=%s machine=%s", dev.id, dev.machine_name)
            return {"agent_id": dev.id, "agent_secret": dev.agent_secret,
                    "machine_name": dev.machine_name}
        finally:
            sess.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Agent 注册失败: %s", e)
        raise HTTPException(status_code=500, detail="注册失败，请稍后重试")


def get_agent(user_id: int) -> WebSocket | None:
    """查找用户对应的在线 Agent 连接：
    1) 旧模式：agent_id == str(user_id) 的直连 Agent（JWT 鉴权，向后兼容）
    2) 机器模式：agent_devices 表里一对一绑定该用户的设备
    """
    ws = _get_connected(str(user_id))
    if ws:
        return ws
    bound_id = _get_bound_agent_id(user_id)
    if bound_id:
        return _get_connected(bound_id)
    return None


def _get_connected(agent_id: str) -> WebSocket | None:
    ws = _agents.get(agent_id)
    if ws and ws.client_state.name == "CONNECTED":
        return ws
    return None


# 绑定关系缓存：user_id -> (agent_id, ts)，30s TTL（避免每次对话请求都查库）
_bind_cache: Dict[int, tuple] = {}


def _get_bound_agent_id(user_id: int) -> str | None:
    """查询该用户一对一绑定的启用设备 id"""
    now = time.time()
    hit = _bind_cache.get(user_id)
    if hit and now - hit[1] < 30:
        return hit[0]
    try:
        from db.session import get_db, AgentDevice
        db = get_db()
        sess = db.Session()
        try:
            dev = sess.query(AgentDevice).filter_by(user_id=user_id, enabled=1).first()
            result = str(dev.id) if dev else None
        finally:
            sess.close()
        _bind_cache[user_id] = (result, now)
        return result
    except Exception as e:
        logger.warning("查询设备绑定失败: %s", e)
        return None


def invalidate_bind_cache(user_id: int):
    """绑定变更后清除缓存"""
    _bind_cache.pop(user_id, None)


def _verify_agent_secret(agent_id: str, secret: str) -> bool:
    """机器模式鉴权：agent_secret 与设备表匹配且设备启用"""
    if not secret or not agent_id.isdigit():
        return False
    try:
        from db.session import get_db, AgentDevice
        db = get_db()
        sess = db.Session()
        try:
            dev = sess.query(AgentDevice).filter_by(id=int(agent_id), enabled=1).first()
            return bool(dev) and bool(dev.agent_secret) and \
                secrets.compare_digest(dev.agent_secret, secret)
        finally:
            sess.close()
    except Exception as e:
        logger.warning("设备鉴权查询失败: %s", e)
        return False


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
    # 在 accept 前验证凭据：JWT（旧模式）或 agent_secret（机器模式，二选一）
    from api.v1.auth.utils import verify_token
    token = websocket.query_params.get("token", "")
    payload = verify_token(token)
    if payload:
        # 旧模式：JWT，user_id 必须等于 agent_id
        if str(payload.get("user_id", "")) != agent_id:
            await websocket.close(code=4003, reason="token 与 agent_id 不匹配")
            return
    elif _verify_agent_secret(agent_id, token):
        pass  # 机器模式：agent_secret 校验通过
    else:
        await websocket.close(code=4001, reason="token 无效或未提供")
        return

    await websocket.accept()
    _agents[agent_id] = websocket
    logger.info("Agent %s 已连接（当前在线: %d）", agent_id, len(_agents))

    # 机器模式：更新设备 last_seen
    if agent_id.isdigit():
        try:
            from db.session import get_db, AgentDevice
            db = get_db()
            sess = db.Session()
            try:
                dev = sess.query(AgentDevice).filter_by(id=int(agent_id)).first()
                if dev:
                    dev.last_seen = datetime.utcnow()
                    sess.commit()
            finally:
                sess.close()
        except Exception:
            pass

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
