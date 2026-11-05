"""Agent WebSocket Hub：管理本地 Agent 连接，中继消息"""

import asyncio
import json
import logging
import os
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

# REST 上报的活动（O1 观测 2026-10-26）：无 WS 连接的轻量客户端（yuancc hooks）
# 经 /agent/activity 上报的元数据活动——agent_id → [{message, detail, time}]（最近 20 条）
_rest_activities: Dict[str, list] = {}

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
            entry["activities"] = _merged_activities(agent_id)
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
                entry["activities"] = _merged_activities(bridge_id)
            result.append(entry)

    # O3（2026-10-26）：REST 上报的离线设备活动（yuancc hooks 无 WS 连接）——
    # 设备离线也把「在干活」展示出来（标注离线上报）
    if include_activities:
        for agent_id in list(_rest_activities.keys()):
            if agent_id in _agents:
                continue  # 在线设备已在主循环合并
            if not is_admin and agent_id not in allowed_ids:
                continue
            rest = _rest_activities.get(agent_id, [])
            if not rest:
                continue
            name = agent_id
            if agent_id.isdigit():
                try:
                    from db.session import get_db, AgentDevice
                    db = get_db()
                    with db.session() as sess:
                        dev = sess.query(AgentDevice).filter_by(id=int(agent_id)).first()
                        if dev:
                            name = dev.machine_name or agent_id
                except Exception:
                    pass
            result.append({
                "agent_id": agent_id,
                "agent_name": f"{name}（离线上报）",
                "capabilities": [],
                "online": False,
                "last_heartbeat": "",
                "activities": list(reversed(rest[-10:])),
            })
    return result


def _merged_activities(agent_id: str) -> list:
    """WS 活动与 REST 上报活动合并（O3 2026-10-26）：按时间排序取最近 10 条倒序"""
    acts = list(_agent_info.get(agent_id, {}).get("activities", []))
    acts += list(_rest_activities.get(agent_id, []))
    acts.sort(key=lambda a: a.get("time", ""))
    return list(reversed(acts[-10:]))


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
    """查询该用户绑定的启用设备 id（N1 多设备：在线设备优先，否则最近活跃）"""
    now = time.time()
    hit = _bind_cache.get(user_id)
    if hit and now - hit[1] < 30:
        return hit[0]
    try:
        from db.session import get_db, AgentDevice
        db = get_db()
        with db.session() as sess:
            devs = (sess.query(AgentDevice)
                    .filter(AgentDevice.user_id == user_id, AgentDevice.enabled == 1,
                            AgentDevice.agent_secret != "")
                    .all())
            result = None
            if devs:
                # 在线设备优先（_agents 内存表）
                for dev in devs:
                    if _get_connected(str(dev.id)):
                        result = str(dev.id)
                        break
                if not result:
                    # 全部离线：选最近活跃（last_seen 最新；从未心跳按 id 最新）
                    devs_sorted = sorted(
                        devs, key=lambda d: (d.last_seen or d.create_time or datetime.min), reverse=True)
                    result = str(devs_sorted[0].id)
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


class ActivityReport(BaseModel):
    """活动上报体（O1 2026-10-26）：只收元数据——state 六态词汇 / tool 工具名 /
    message 展示文案 / detail 补充。绝不上传命令内容、文件内容、对话正文。"""
    state: str = ""      # thinking/working/attention/error/idle/sleeping
    tool: str = ""
    message: str = ""
    detail: str = ""


@router.get("/my-code")
async def my_agent_code(request: Request):
    """自服务安装码（2026-10-30，登录可见）：普通用户没有后台——下载后在此自取。
    码生成时即预绑定 user_id（本机注册后自动归属该用户，无需管理员绑定）。"""
    uid = getattr(request.state, "user_id", None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    from db.session import get_db, AgentDevice
    db = get_db()
    with db.session() as sess:
        # N1（2026-11-06）：一账号多设备——设备数未达上限即可再发码（换电脑零迁移）
        from config.settings import AGENT_MAX_DEVICES_PER_USER
        bound_devs = sess.query(AgentDevice).filter(AgentDevice.user_id == uid,
                                                    AgentDevice.agent_secret != "").all()
        pending = sess.query(AgentDevice).filter(AgentDevice.user_id == uid,
                                                 AgentDevice.agent_secret == "").first()
        if pending:
            return {"code": pending.install_code, "bound": False,
                    "device_count": len(bound_devs),
                    "max_devices": AGENT_MAX_DEVICES_PER_USER,
                    "machine_names": [d.machine_name or f"设备{d.id}" for d in bound_devs],
                    "message": "请在本机 Agent 安装引导中输入该安装码"}
        if len(bound_devs) >= AGENT_MAX_DEVICES_PER_USER:
            return {"code": "", "bound": True,
                    "device_count": len(bound_devs),
                    "max_devices": AGENT_MAX_DEVICES_PER_USER,
                    "machine_names": [d.machine_name or f"设备{d.id}" for d in bound_devs],
                    "message": f"已绑定 {len(bound_devs)} 台设备（上限 {AGENT_MAX_DEVICES_PER_USER} 台）——换新电脑请先在后台解绑旧设备"}
        # 生成新码（预绑定）
        code = "YUAN-" + "-".join(secrets.token_hex(2).upper() for _ in range(3))
        sess.add(AgentDevice(install_code=code, agent_secret="", user_id=uid))
        sess.commit()
        return {"code": code, "bound": False,
                "device_count": len(bound_devs),
                "max_devices": AGENT_MAX_DEVICES_PER_USER,
                "machine_names": [d.machine_name or f"设备{d.id}" for d in bound_devs],
                "message": "请在本机 Agent 安装引导中输入该安装码"}


@router.post("/my-code")
async def reset_my_agent_code(request: Request):
    """重置安装码（2026-10-30）：生成新码并解绑旧设备（换电脑场景，旧电脑失效）"""
    uid = getattr(request.state, "user_id", None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    from db.session import get_db, AgentDevice
    db = get_db()
    with db.session() as sess:
        # 解绑旧设备 + 清未用旧码
        for dev in sess.query(AgentDevice).filter(AgentDevice.user_id == uid).all():
            dev.user_id = None
        code = "YUAN-" + "-".join(secrets.token_hex(2).upper() for _ in range(3))
        sess.add(AgentDevice(install_code=code, agent_secret="", user_id=uid))
        sess.commit()
        from api.v1.agent.router import invalidate_bind_cache
        invalidate_bind_cache(uid)
        return {"code": code, "message": "新安装码已生成，旧设备已解绑（旧电脑将失效）"}


@router.get("/downloads")
async def agent_downloads(request: Request):
    """用户侧 Agent 下载清单（2026-10-30，登录可见）：全部版本 + 默认标记。
    普通用户下载入口（设置页「本地 Agent 下载」卡）消费本端点。"""
    uid = getattr(request.state, "user_id", None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    from api.v1.admin.agent_devices import _load_versions
    data = _load_versions()
    return {"default_version": data.get("default_version", ""), "versions": data["versions"]}


@router.get("/download-exe")
async def agent_download_exe(request: Request, code: str = ""):
    """T2 免输码自动注册（2026-11-06）：带码下载——文件名内嵌预绑定安装码
    yuanai-agent-v{版本}_{安装码}.exe，Agent 首启从自身文件名解析静默注册。

    安全：码必须预绑定当前登录用户（my-code/后台签发时 user_id 归属）；
    文件本身是静态目录同一份 exe，仅 Content-Disposition 文件名不同——
    不扩大暴露面（码本就一次消费）。"""
    uid = getattr(request.state, "user_id", None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    code = (code or "").strip().upper()
    from db.session import get_db, AgentDevice
    from api.v1.admin.agent_devices import _load_versions, _downloads_dir
    if code:
        with get_db().session() as sess:
            dev = sess.query(AgentDevice).filter_by(install_code=code).first()
            if not dev or (dev.user_id or 0) != uid:
                raise HTTPException(status_code=403, detail="安装码不属于当前账号")
    data = _load_versions()
    default = next((v for v in data["versions"]
                    if v["version"] == data.get("default_version")), None)
    if not default and data["versions"]:
        default = data["versions"][-1]
    if not default:
        raise HTTPException(status_code=404, detail="暂无可用版本")
    fpath = os.path.join(_downloads_dir(), "versions", default["filename"])
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="版本文件不存在")
    fname = default["filename"] if not code else         f"yuanai-agent-v{default['version']}_{code}.exe"
    from fastapi.responses import FileResponse
    return FileResponse(fpath, media_type="application/octet-stream",
                        filename=fname)


@router.post("/activity")
async def report_activity(req: ActivityReport, request: Request):
    """无 WS 客户端（yuancc hooks 等）的元数据活动上报——设备凭据鉴权，
    与 WS activity 事件同口径进该设备活动流；设备离线时活动仍记录展示。"""
    try:
        agent_id = require_agent_device(request)
        state = req.state.strip()[:32]
        tool = req.tool.strip()[:64]
        message = req.message.strip()[:120]
        detail = req.detail.strip()[:120]
        # message 缺省时由 state/tool 推导（六态词汇中文映射）
        if not message:
            _state_zh = {"thinking": "思考中", "working": "工具调用", "attention": "等待审批",
                         "error": "出错", "idle": "空闲", "sleeping": "休眠"}
            message = _state_zh.get(state, state or "活动")
            if tool:
                message = f"{message}: {tool}"
        acts = _rest_activities.setdefault(agent_id, [])
        acts.append({"message": message, "detail": detail, "time": time.strftime("%H:%M:%S"),
                     "source": "rest"})
        if len(acts) > 20:
            acts[:] = acts[-20:]
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("活动上报失败: %s", e)
        raise HTTPException(status_code=500, detail="活动上报失败")


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


class UsageUploadBody(BaseModel):
    rows: list = []


@router.post("/usage")
def agent_usage_upload(request: Request, body: UsageUploadBody):
    """部署 Agent 的用量上传（本地 Agent 无 MySQL，统筹/自动化/审核等 LLM 用量
    经 HTTP 由云端落库 token_usage；2026-10-22 补——此前部署 Agent 用量全部丢失）。

    行校验：model/purpose/source 截断，token 非负整数，单批 ≤200 行防滥用。
    """
    require_agent_device(request)
    from db.session import get_db
    rows = []
    for r in (body.rows or [])[:200]:
        if not isinstance(r, dict):
            continue
        try:
            rows.append({
                "user_id": max(int(r.get("user_id") or 0), 0),
                "model": str(r.get("model") or "")[:64],
                "purpose": str(r.get("purpose") or "chat")[:32],
                "prompt_tokens": max(int(r.get("prompt_tokens") or 0), 0),
                "completion_tokens": max(int(r.get("completion_tokens") or 0), 0),
                "total_tokens": max(int(r.get("total_tokens") or 0), 0),
                "cache_hit_tokens": max(int(r.get("cache_hit_tokens") or 0), 0),
                "source": str(r.get("source") or "agent")[:16],
            })
        except (TypeError, ValueError):
            continue
    if rows:
        get_db().add_token_usage_rows(rows)
    return {"ok": True, "added": len(rows)}


@router.post("/bridge-memory")
def bridge_memory(request: Request, body: BridgeMemoryBody):
    """CC 桥接记忆写入：Agent 凭据校验 → 对 user_id 合并事实进长期记忆。

    C2 安全修复（2026-10-29）：此前任意注册设备凭据即可对任意 user_id
    写记忆（IDOR）。现在只允许桥接专用设备（agent_id == CLAUDE_BRIDGE_AGENT_ID）
    写指定用户记忆；普通设备一律走绑定语义的 /memory 端点。
    """
    agent_id = require_agent_device(request)
    from config.settings import CLAUDE_BRIDGE_AGENT_ID
    if str(CLAUDE_BRIDGE_AGENT_ID or "") != str(agent_id):
        raise HTTPException(status_code=403, detail="仅桥接专用设备可写指定用户记忆")
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
    """本地 Agent 记忆读取（get_user_memory 工具走 HTTP；data/.yuan/ 文件存储）。

    C2 安全修复（2026-10-29）：目标用户强制为设备一对一绑定用户——
    忽略调用方传入的任意 user_id（此前 IDOR：任何设备凭据可读他人记忆）。
    """
    uid = require_agent_uid(request)
    from db.session import get_db
    memory = get_db().get_user_memory(uid)
    return {"ok": True, "memory": memory}


@router.post("/memory")
def agent_add_memory(request: Request, body: AgentMemoryBody):
    """本地 Agent 记忆写入（remember_user_info 工具走 HTTP；合并语义同折叠）。

    C2 安全修复（2026-10-29）：目标用户强制为设备绑定用户（忽略 body.user_id）。
    """
    uid = require_agent_uid(request)
    if not body.facts:
        return {"ok": True, "added": 0}
    facts = [str(f)[:200] for f in body.facts[:20] if str(f).strip()]
    if not facts:
        return {"ok": True, "added": 0}
    from config.settings import MEMORY_MAX_ITEMS, MEMORY_MAX_CHARS
    from db.session import get_db
    r = get_db().merge_user_memory(uid, facts, MEMORY_MAX_ITEMS, MEMORY_MAX_CHARS)
    return {"ok": True, "added": r["added"]}


class AgentOrganizeBody(BaseModel):
    user_id: int = 0
    session_id: str = ""
    items: list = []


@router.post("/memory/organize")
def agent_organize_memory(request: Request, body: AgentOrganizeBody):
    """本地 Agent 记忆自整理（organize_user_memory 工具走 HTTP；删除护栏在 db 层）。

    C2 安全修复（2026-10-29）：目标用户强制为设备绑定用户。
    """
    uid = require_agent_uid(request)
    from db.session import get_db
    r = get_db().organize_user_memory(uid, body.items, body.session_id)
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("detail", "整理失败"))
    return {"ok": True, "deleted": r["deleted"], "total": r["total"]}


@router.delete("/memory")
def agent_delete_memory(request: Request, body: AgentMemoryBody):
    """本地 Agent 记忆删除（forget_user_info 工具走 HTTP；多条命中不误删）。

    C2 安全修复（2026-10-29）：目标用户强制为设备绑定用户。
    """
    uid = require_agent_uid(request)
    if not body.line.strip():
        raise HTTPException(status_code=400, detail="缺少 line")
    from db.session import get_db
    r = get_db().delete_user_memory_line(uid, body.line.strip())
    if r["asked_more"]:
        raise HTTPException(status_code=400, detail="匹配到多条记忆，请说得更具体")
    if r["deleted"] == 0:
        return {"ok": True, "deleted": 0}
    return {"ok": True, "deleted": r["deleted"], "memory": r["memory"]}
