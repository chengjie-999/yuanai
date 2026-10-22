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
# request_id → agent_id（2026-10-19：断线清理按归属而非 UUID startswith）
_pending_owner: Dict[str, str] = {}

HEARTBEAT_INTERVAL = 30


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
            # vault 同步状态（前端知识星球页徽标；无该键 = 未启用）
            "vault_sync": info.get("vault_sync", {}),
            "vault_sync_time": info.get("vault_sync_time", ""),
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
        with db.session() as sess:
            dev = sess.query(AgentDevice).filter_by(install_code=code).first()
            # S3.5：两种失败统一文案与状态码（防安装码枚举 oracle 区分「不存在」与「已使用」）
            if not dev or dev.agent_secret:
                raise HTTPException(status_code=400, detail="安装码无效或已被使用")
            dev.agent_secret = secrets.token_hex(32)
            dev.machine_name = (req.machine_name or "")[:64]
            dev.last_seen = datetime.utcnow()
            sess.commit()
            logger.info("Agent 设备注册: id=%s machine=%s", dev.id, dev.machine_name)
            return {"agent_id": dev.id, "agent_secret": dev.agent_secret,
                    "machine_name": dev.machine_name}
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
        with db.session() as sess:
            dev = sess.query(AgentDevice).filter_by(user_id=user_id, enabled=1).first()
            result = str(dev.id) if dev else None
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
        with db.session() as sess:
            dev = sess.query(AgentDevice).filter_by(id=int(agent_id), enabled=1).first()
            return bool(dev) and bool(dev.agent_secret) and \
                secrets.compare_digest(dev.agent_secret, secret)
    except Exception as e:
        logger.warning("设备鉴权查询失败: %s", e)
        return False


def resolve_agent_uid(agent_id: str) -> int:
    """机器设备 → 一对一绑定的云端用户 id（vault 同步等 REST 端点用）；未绑定返回 0"""
    if not agent_id.isdigit():
        return 0
    try:
        from db.session import get_db, AgentDevice
        db = get_db()
        with db.session() as sess:
            dev = sess.query(AgentDevice).filter_by(id=int(agent_id), enabled=1).first()
            return (dev.user_id or 0) if dev else 0
    except Exception as e:
        logger.warning("设备绑定查询失败: %s", e)
        return 0


def require_agent_device(request: Request) -> str:
    """设备凭据校验统一入口（2026-10-21 清洁3）：X-Agent-Id + X-Agent-Secret 头
    → _verify_agent_secret；通过返回 agent_id，失败 401。
    四份重复校验（bridge-memory/memory/planet_sync/plan_sync）合一本。"""
    agent_id = request.headers.get("X-Agent-Id", "")
    secret = request.headers.get("X-Agent-Secret", "")
    if not _verify_agent_secret(agent_id, secret):
        raise HTTPException(status_code=401, detail="Agent 凭据无效")
    return agent_id


def require_agent_uid(request: Request) -> int:
    """设备凭据 + 一对一绑定映射 → 用户 ID（planet/plan 同步端点用）；未绑定 403"""
    agent_id = require_agent_device(request)
    uid = resolve_agent_uid(agent_id)
    if not uid:
        raise HTTPException(status_code=403, detail="设备未绑定账号")
    return uid


def get_pending_queue(request_id: str) -> asyncio.Queue:
    """为指定 request_id 获取或创建等待队列"""
    if request_id not in _pending:
        _pending[request_id] = asyncio.Queue()
    return _pending[request_id]


def cleanup_pending(request_id: str):
    """清理已完成请求的队列"""
    _pending.pop(request_id, None)
    _pending_owner.pop(request_id, None)


@router.websocket("/ws/agent/{agent_id}")
async def agent_ws(websocket: WebSocket, agent_id: str):
    # 在 accept 前验证凭据：JWT（旧模式）或 agent_secret（机器模式，二选一）
    # S3.3：token 优先取 Authorization 头（不落 URL/日志）；?token= 兜底保留一个版本
    from api.v1.auth.utils import verify_token
    auth = websocket.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    token = token or websocket.query_params.get("token", "")
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
            with db.session() as sess:
                dev = sess.query(AgentDevice).filter_by(id=int(agent_id)).first()
                if dev:
                    dev.last_seen = datetime.utcnow()
                    sess.commit()
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

            if event_type == "vault_sync":
                # Obsidian vault 同步状态（前端知识星球页徽标轮询展示）
                if agent_id in _agent_info:
                    _agent_info[agent_id]["vault_sync"] = event.get("data", {})
                    _agent_info[agent_id]["vault_sync_time"] = time.strftime("%H:%M:%S")
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
            # 清理该 agent 关联的所有 pending 请求。
            # 2026-10-19 修复：request_id 是 UUID，startswith(agent_id) 永不匹配
            # （且数字 id 前缀可能误删他人）——改为按注册连接的 agent 归属表清理
            stale = [rid for rid, a in list(_pending_owner.items())
                     if a == agent_id and rid in _pending]
            for rid in stale:
                cleanup_pending(rid)
            logger.info("Agent %s 已移除（当前在线: %d）", agent_id, len(_agents))


async def _heartbeat(websocket: WebSocket, agent_id: str):
    """定期发送 ping，检测 Agent 是否存活；同时刷新设备 last_seen
    （计划工具的在线判定用——此前只在连接时写一次，几十分钟后判离线）"""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                await websocket.send_json({"type": "ping"})
                if agent_id.isdigit():
                    try:
                        from db.session import get_db, AgentDevice
                        sess = get_db().Session()
                        try:
                            dev = sess.query(AgentDevice).filter_by(id=int(agent_id)).first()
                            if dev:
                                dev.last_seen = datetime.utcnow()
                                sess.commit()
                        finally:
                            sess.close()
                    except Exception:
                        pass
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

    # 预创建等待队列 + 记录归属 agent（断线清理用；机器模式 agent_id≠user_id，
    # 按 socket 反查真实 agent_id）
    get_pending_queue(request_id)
    _pending_owner[request_id] = next(
        (aid for aid, w in _agents.items() if w is ws), str(user_id))

    try:
        await ws.send_json(chat_request)
        return request_id
    except Exception as e:
        logger.error("向 Agent 转发消息失败: %s", e)
        cleanup_pending(request_id)
        return None


async def send_stop_to_agent(user_id: int, request_id: str) -> bool:
    """B1-12 停止联动：用户中断 SSE（停止生成）时通知本地 Agent 终止该请求的脚本子进程"""
    if not user_id or not request_id:
        return False
    ws = get_agent(user_id)
    if ws is None:
        return False
    try:
        await ws.send_json({"type": "stop_request", "request_id": request_id})
        return True
    except Exception as e:
        logger.warning("向 Agent 发送停止通知失败: %s", e)
        return False


class BridgeMemoryBody(BaseModel):
    user_id: int = 0
    facts: list = []


class KnowledgeSearchBody(BaseModel):
    query: str = ""
    user_id: int = 0
    top_k: int = 5


@router.post("/knowledge/search")
def agent_knowledge_search(request: Request, body: KnowledgeSearchBody):
    """部署 Agent 的知识库检索（本地 Agent 无云端 Milvus，经 HTTP 由云端执行；
    曾直连本机 Milvus 连接重试挂死卡对话 120s，2026-10-22 改云端执行）。
    user_id 由设备绑定推导（同 plan_sync）；请求体 user_id 仅作冗余校验。"""
    uid = require_agent_uid(request)
    if body.user_id and body.user_id != uid:
        raise HTTPException(status_code=403, detail="user_id 与设备绑定不符")
    query = (body.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="缺少 query")
    from yuanai_core.rag import search_knowledge
    text = search_knowledge(query, top_k=max(1, min(int(body.top_k or 5), 20)), user_id=uid)
    return {"ok": True, "text": text}


@router.post("/bridge-memory")
def bridge_memory(request: Request, body: BridgeMemoryBody):
    """CC 桥接记忆写入：Agent 凭据校验 → 对 user_id 合并事实进长期记忆。

    安全边界：持有设备 secret 即持有写权限（桥接设备属于站主），
    调用方（claude_bridge）只传 chat_request 里的真实 user_id。
    """
    require_agent_device(request)
    if not body.user_id or not body.facts:
        return {"ok": True, "added": 0}

    facts = [str(f)[:200] for f in body.facts[:20] if str(f).strip()]
    if not facts:
        return {"ok": True, "added": 0}

    from config.settings import MEMORY_MAX_ITEMS, MEMORY_MAX_CHARS
    from db.session import get_db
    r = get_db().merge_user_memory(body.user_id, facts, MEMORY_MAX_ITEMS, MEMORY_MAX_CHARS)
    return {"ok": True, "added": r["added"]}


class AgentMemoryBody(BaseModel):
    user_id: int = 0
    line: str = ""
    facts: list = []


@router.get("/memory")
def agent_get_memory(request: Request, user_id: int = 0):
    """本地 Agent 记忆读取（get_user_memory 工具走 HTTP；data/.yuan/ 文件存储）"""
    require_agent_device(request)
    if not user_id:
        raise HTTPException(status_code=400, detail="缺少 user_id")
    from db.session import get_db
    memory = get_db().get_user_memory(user_id)
    return {"ok": True, "memory": memory}


@router.post("/memory")
def agent_add_memory(request: Request, body: AgentMemoryBody):
    """本地 Agent 记忆写入（remember_user_info 工具走 HTTP；合并语义同折叠）"""
    require_agent_device(request)
    if not body.user_id or not body.facts:
        return {"ok": True, "added": 0}
    facts = [str(f)[:200] for f in body.facts[:20] if str(f).strip()]
    if not facts:
        return {"ok": True, "added": 0}
    from config.settings import MEMORY_MAX_ITEMS, MEMORY_MAX_CHARS
    from db.session import get_db
    r = get_db().merge_user_memory(body.user_id, facts, MEMORY_MAX_ITEMS, MEMORY_MAX_CHARS)
    return {"ok": True, "added": r["added"]}


class AgentOrganizeBody(BaseModel):
    user_id: int = 0
    session_id: str = ""
    items: list = []


@router.post("/memory/organize")
def agent_organize_memory(request: Request, body: AgentOrganizeBody):
    """本地 Agent 记忆自整理（organize_user_memory 工具走 HTTP；删除护栏在 db 层）"""
    require_agent_device(request)
    if not body.user_id:
        raise HTTPException(status_code=400, detail="缺少 user_id")
    from db.session import get_db
    r = get_db().organize_user_memory(body.user_id, body.items, body.session_id)
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("detail", "整理失败"))
    return {"ok": True, "deleted": r["deleted"], "total": r["total"]}


@router.delete("/memory")
def agent_delete_memory(request: Request, body: AgentMemoryBody):
    """本地 Agent 记忆删除（forget_user_info 工具走 HTTP；多条命中不误删）"""
    require_agent_device(request)
    if not body.user_id or not body.line.strip():
        raise HTTPException(status_code=400, detail="缺少 user_id 或 line")
    from db.session import get_db
    r = get_db().delete_user_memory_line(body.user_id, body.line.strip())
    if r["asked_more"]:
        raise HTTPException(status_code=400, detail="匹配到多条记忆，请说得更具体")
    if r["deleted"] == 0:
        return {"ok": True, "deleted": 0}
    return {"ok": True, "deleted": r["deleted"], "memory": r["memory"]}
