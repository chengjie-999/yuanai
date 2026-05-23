import base64
from datetime import datetime, timedelta
import os
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from db.session import get_db
from api.v1.middleware import require_admin
from utils.data_path import root_path

router = APIRouter(prefix="/admin", tags=["admin"])


class FreezeRequest(BaseModel):
    user_id: int
    days: int


class AdminCreateUser(BaseModel):
    username: str
    password: str
    role: str = 'user'


class WebsiteCreate(BaseModel):
    name: str
    url: str
    remark: str = ""
    sort_order: int = 0


class WebsiteUpdate(BaseModel):
    name: str = None
    url: str = None
    remark: str = None
    sort_order: int = None


# ===================== 用户管理 =====================


@router.get("/users")
async def list_users(request: Request):
    require_admin(request)
    db = get_db()
    from db.session import User
    sess = db.Session()
    try:
        users = sess.query(User).order_by(User.id).all()
        now = datetime.utcnow()
        return [{
            "id": u.id, "username": u.username, "display_name": u.display_name or "",
            "role": u.role,
            "frozen": u.frozen_until is not None and u.frozen_until > now,
            "frozen_until": str(u.frozen_until)[:19] if u.frozen_until else None,
            "create_time": str(u.create_time)[:19] if u.create_time else "",
        } for u in users]
    finally:
        sess.close()


@router.post("/users/freeze")
async def freeze_user(req: FreezeRequest, request: Request):
    require_admin(request)
    if req.days < 0:
        raise HTTPException(status_code=400, detail="天数不能为负数")
    db = get_db()
    from db.session import User
    sess = db.Session()
    try:
        user = sess.query(User).filter_by(id=req.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user.role == "admin":
            raise HTTPException(status_code=400, detail="不能冻结管理员")
        if req.days == 0:
            user.frozen_until = None
            msg = f"已解冻用户 {user.username}"
        else:
            user.frozen_until = datetime.utcnow() + timedelta(days=req.days)
            msg = f"已冻结用户 {user.username} {req.days} 天"
        sess.commit()
        return {"ok": True, "message": msg}
    finally:
        sess.close()


@router.post("/users/create")
async def admin_create_user(req: AdminCreateUser, request: Request):
    """管理员创建新用户"""
    require_admin(request)
    db = get_db()
    result = db.register_user(req.username, req.password, role=req.role)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/users/{user_id}")
async def admin_delete_user(user_id: int, request: Request):
    """删除普通用户（仅 admin，不能删除 admin 和自己）"""
    require_admin(request)
    if user_id == getattr(request.state, "user_id", 0):
        raise HTTPException(status_code=400, detail="不能删除自己")
    from db.session import User
    db = get_db()
    sess = db.Session()
    try:
        user = sess.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user.role == "admin":
            raise HTTPException(status_code=400, detail="不能删除管理员")
        sess.delete(user)
        sess.commit()
        return {"ok": True, "deleted": user.username}
    finally:
        sess.close()


# ===================== 网站管理 =====================


@router.get("/websites")
async def list_websites(request: Request):
    require_admin(request)
    db = get_db()
    websites = db.get_websites()
    if not websites:
        # 数据库为空时，从 spiderlx 注册表自动导入
        try:
            from spiderlx.core.save.urls import get_urls
            get_urls()
            websites = db.get_websites()
        except ImportError:
            pass
    return websites


@router.post("/websites")
async def add_website(req: WebsiteCreate, request: Request):
    require_admin(request)
    db = get_db()
    result = db.add_website(req.name, req.url, req.remark, req.sort_order)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.put("/websites/{wid}")
async def edit_website(wid: int, req: WebsiteUpdate, request: Request):
    require_admin(request)
    db = get_db()
    ok = db.update_website(wid, req.name, req.url, req.remark, req.sort_order)
    if not ok:
        raise HTTPException(status_code=404, detail="网站不存在")
    return {"ok": True}


@router.delete("/websites/{wid}")
async def delete_website(wid: int, request: Request):
    require_admin(request)
    db = get_db()
    ok = db.delete_website(wid)
    if not ok:
        raise HTTPException(status_code=404, detail="网站不存在")
    return {"ok": True}


# ===================== 文件管理 =====================


@router.get("/files")
async def list_files(request: Request, path: str = ""):
    require_admin(request)
    base = os.path.realpath(os.path.join(root_path(), "data"))
    target = os.path.realpath(os.path.join(base, path))
    if not target.startswith(base + os.sep) and target != base:
        raise HTTPException(status_code=400, detail="路径越权")
    if not os.path.exists(target):
        return {"path": path, "items": []}
    items = []
    for name in sorted(os.listdir(target)):
        full = os.path.join(target, name)
        rel = os.path.join(path, name) if path else name
        is_dir = os.path.isdir(full)
        size = 0 if is_dir else os.path.getsize(full)
        items.append({"name": name, "path": rel, "is_dir": is_dir, "size_kb": round(size / 1024, 1)})
    return {"path": path, "items": items}


@router.get("/file/read")
async def read_file(request: Request, path: str = ""):
    """读取文件内容（图片返回 base64，文本返回内容）"""
    require_admin(request)
    base = os.path.realpath(os.path.join(root_path(), "data"))
    target = os.path.realpath(os.path.join(base, path))
    if not target.startswith(base + os.sep) and target != base:
        raise HTTPException(status_code=400, detail="路径越权")
    if not os.path.isfile(target):
        raise HTTPException(status_code=404, detail="文件不存在")
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
        with open(target, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        return {"type": "image", "ext": ext, "data": b64}
    if ext in ('.txt', '.csv', '.json', '.py', '.js', '.tsx', '.ts', '.css', '.html', '.md', '.yml', '.yaml', '.xml', '.log'):
        try:
            with open(target, 'r', encoding='utf-8') as f:
                text = f.read()
            return {"type": "text", "content": text}
        except UnicodeDecodeError:
            return {"type": "binary", "detail": "无法解码为文本"}
    return {"type": "unsupported", "detail": f"暂不支持预览 {ext} 文件"}


# ===================== 仪表盘 =====================


@router.get("/dashboard")
async def admin_dashboard(request: Request):
    db = get_db()
    sess = db.Session()
    try:
        from db.session import User, ChatSession, AIChat
        from sqlalchemy import func

        user_count = sess.query(func.count(User.id)).scalar() or 0
        session_count = sess.query(func.count(ChatSession.id)).scalar() or 0
        message_count = sess.query(func.count(AIChat.id)).scalar() or 0

        # 最近30天消息数
        from datetime import datetime as dt, timedelta
        thirty_days_ago = dt.utcnow() - timedelta(days=30)
        daily = (
            sess.query(
                func.date(AIChat.create_time).label("date"),
                func.count(AIChat.id).label("count"),
            )
            .filter(AIChat.create_time >= thirty_days_ago)
            .group_by(func.date(AIChat.create_time))
            .order_by(func.date(AIChat.create_time))
            .all()
        )
        daily_messages = [{"date": str(d), "count": c} for d, c in daily]

        # 今日统计
        today = dt.utcnow().strftime("%Y-%m-%d")
        today_messages = sess.query(func.count(AIChat.id)).filter(
            func.date(AIChat.create_time) == today
        ).scalar() or 0
        today_users = sess.query(func.count(func.distinct(AIChat.session_id))).filter(
            func.date(AIChat.create_time) == today
        ).scalar() or 0
        avg_msgs = round(message_count / max(session_count, 1), 1)

        # 数据集数
        import os
        from utils.data_path import root_path
        ds_dir = os.path.join(root_path(), "data", "datasets")
        dataset_count = len(os.listdir(ds_dir)) if os.path.isdir(ds_dir) else 0

        return {
            "users": user_count,
            "sessions": session_count,
            "messages": message_count,
            "today_messages": today_messages,
            "today_users": today_users,
            "avg_messages": avg_msgs,
            "datasets": dataset_count,
            "daily_messages": daily_messages,
        }
    finally:
        sess.close()


# ===================== 会话管理 =====================


@router.get("/sessions")
async def admin_list_sessions(request: Request):
    """返回全部用户会话（admin only），按更新时间倒序"""
    require_admin(request)
    db = get_db()
    sess = db.Session()
    try:
        from db.session import ChatSession, AIChat, User
        from sqlalchemy import func

        rows = (
            sess.query(
                ChatSession.session_id,
                ChatSession.title,
                ChatSession.create_time,
                ChatSession.update_time,
                User.username,
                func.count(AIChat.id).label("message_count"),
            )
            .outerjoin(AIChat, AIChat.session_id == ChatSession.session_id)
            .outerjoin(User, User.id == ChatSession.user_id)
            .group_by(
                ChatSession.session_id,
                ChatSession.title,
                ChatSession.create_time,
                ChatSession.update_time,
                User.username,
            )
            .order_by(ChatSession.update_time.desc())
            .limit(200)
            .all()
        )
        return [
            {
                "session_id": r.session_id,
                "title": r.title,
                "username": r.username or "-",
                "message_count": r.message_count,
                "create_time": str(r.create_time)[:19] if r.create_time else "",
                "update_time": str(r.update_time)[:19] if r.update_time else "",
            }
            for r in rows
        ]
    finally:
        sess.close()


# ===================== Agent 状态摘要 =====================


@router.get("/agent-summary")
async def admin_agent_summary(request: Request):
    from api.v1.agent.router import _agents, _agent_info

    result = []
    for agent_id, ws in _agents.items():
        info = _agent_info.get(agent_id, {})
        online = ws.client_state.name == "CONNECTED" if hasattr(ws, 'client_state') else False
        result.append({
            "agent_id": agent_id,
            "agent_name": info.get("agent_name", agent_id),
            "capabilities": info.get("capabilities", []),
            "online": online,
            "last_heartbeat": info.get("last_heartbeat", ""),
        })
    return result


# ===================== 模型配置 =====================


def _read_models_file() -> dict:
    import json, os
    from utils.data_path import root_path
    path = os.path.join(root_path(), "data", "models.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _write_models_file(data: dict):
    import json, os
    from utils.data_path import root_path
    path = os.path.join(root_path(), "data", "models.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class ModelUpsert(BaseModel):
    model_id: str
    label: str
    provider: str = "Custom"

@router.get("/models")
async def list_models(request: Request):
    from config.settings import MODELS, _DEFAULT_MODELS
    result = {}
    for k, v in MODELS.items():
        result[k] = {**v, "builtin": k in _DEFAULT_MODELS}
    return result

@router.post("/models")
async def add_model(req: ModelUpsert, request: Request):
    require_admin(request)
    data = _read_models_file()
    data[req.model_id] = {"label": req.label, "provider": req.provider}
    _write_models_file(data)
    from config.settings import _load_models, MODELS
    MODELS.clear(); MODELS.update(_load_models())
    return {"ok": True, "model_id": req.model_id}

class ModelDelete(BaseModel):
    model_id: str

class ApiKeyUpsert(BaseModel):
    provider: str
    key: str

@router.get("/apikeys")
async def list_apikeys(request: Request):
    require_admin(request)
    return _read_models_file().get("_apikeys", {})

@router.post("/apikeys")
async def save_apikey(req: ApiKeyUpsert, request: Request):
    require_admin(request)
    data = _read_models_file()
    keys = data.get("_apikeys", {})
    keys[req.provider] = req.key
    data["_apikeys"] = keys
    _write_models_file(data)
    return {"ok": True}

@router.delete("/apikeys")
async def delete_apikey(req: ApiKeyUpsert, request: Request):
    require_admin(request)
    data = _read_models_file()
    keys = data.get("_apikeys", {})
    keys.pop(req.provider, None)
    if keys:
        data["_apikeys"] = keys
    else:
        data.pop("_apikeys", None)
    _write_models_file(data)
    return {"ok": True}

@router.delete("/models")
async def delete_model(req: ModelDelete, request: Request):
    require_admin(request)
    data = _read_models_file()
    if req.model_id in data:
        del data[req.model_id]
        _write_models_file(data)
    from config.settings import _load_models, MODELS
    MODELS.clear(); MODELS.update(_load_models())
    return {"ok": True}


# ===================== Agent 状态（代理到 agent router 内部数据）=====================


@router.get("/agent-status")
async def admin_agent_status_v2(request: Request):
    """返回 Agent 列表。admin 看全部，普通用户只看自己的。"""
    from api.v1.agent.router import _agents, _agent_info
    from api.v1.auth.utils import verify_token
    from api.v1.middleware import _extract_token

    token = _extract_token(request)
    payload = verify_token(token) if token else None
    current_user = str(payload.get("user_id", 0)) if payload else "0"
    is_admin = payload.get("role") == "admin" if payload else False

    result = []
    for agent_id, ws in list(_agents.items()):
        if not is_admin and agent_id != current_user:
            continue
        info = _agent_info.get(agent_id, {})
        result.append({
            "agent_id": agent_id,
            "agent_name": info.get("agent_name", agent_id),
            "capabilities": info.get("capabilities", []),
            "online": True,
            "last_heartbeat": info.get("last_heartbeat", ""),
            "activities": list(reversed(info.get("activities", [])[-10:])),
        })
    return result
