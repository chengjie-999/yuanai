import json as _json
import logging
import os as _os
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator
from db.session import get_db
from api.v1.auth.utils import create_token, verify_token
from api.v1.ratelimit import auth_limiter, get_client_ip
from utils.data_path import root_path as _root_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _read_models_file() -> dict:
    path = _os.path.join(_root_path(), "data", "models.json")
    if _os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return _json.load(f)
    return {}


def _write_models_file(data: dict):
    path = _os.path.join(_root_path(), "data", "models.json")
    _os.makedirs(_os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=2)

MAX_LOGIN_ATTEMPTS = 5
LOCK_MINUTES = 15


class AuthRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def strip_username(cls, v: str) -> str:
        """自动去除用户名首尾空格"""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("用户名至少 3 个字符")
        return v

    @field_validator("password")
    @classmethod
    def check_password_length(cls, v: str) -> str:
        """密码最小长度校验"""
        if len(v) < 8:
            raise ValueError("密码至少 8 个字符")
        return v


class RegisterRequest(AuthRequest):
    display_name: str = ""
    role: str = "user"


@router.post("/register")
def register(req: RegisterRequest):
    """注册新用户"""
    raise HTTPException(status_code=403, detail="注册功能暂不开放，请联系管理员创建账号")


@router.post("/login")
def login(req: AuthRequest, request: Request):
    """用户登录（连续失败 5 次锁定 15 分钟）"""
    ip = get_client_ip(request)
    auth_limiter.check(ip)
    db = get_db()

    # 1. 检查账号是否被临时锁定
    user = db.get_user_by_username(req.username)
    if user and user.locked_until and user.locked_until > datetime.utcnow():
        remaining = int((user.locked_until - datetime.utcnow()).total_seconds())
        logger.warning("登录被锁: username=%s, ip=%s, 剩余=%ds", req.username, ip, remaining)
        raise HTTPException(
            status_code=429,
            detail=f"账号已临时锁定，请 {remaining} 秒后重试",
        )

    # 2. 验证密码
    user = db.authenticate_user(req.username, req.password)
    if not user:
        db.record_failed_login(req.username)
        # 重新读取锁定状态用于日志
        updated = db.get_user_by_username(req.username)
        attempts = updated.failed_login_attempts if updated else 0
        logger.warning(
            "登录失败: username=%s, ip=%s, attempts=%d, ua=%s",
            req.username, ip, attempts,
            request.headers.get("User-Agent", "")[:120],
        )
        if updated and updated.locked_until and updated.locked_until > datetime.utcnow():
            raise HTTPException(
                status_code=429,
                detail=f"登录失败次数过多，账号已锁定 {LOCK_MINUTES} 分钟",
            )
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 3. 管理员冻结检查
    if user.frozen_until and user.frozen_until > datetime.utcnow():
        days = (user.frozen_until - datetime.utcnow()).days
        raise HTTPException(status_code=403, detail=f"账号已被冻结，剩余 {days} 天")

    # 4. 登录成功 — 重置失败计数 + 发令牌
    db.reset_login_attempts(user.id)
    if user.failed_login_attempts > 0:
        logger.info("登录成功（锁定解除）: user=%s, ip=%s", user.username, ip)
    else:
        logger.info("登录成功: user=%s, ip=%s", user.username, ip)

    token = create_token(user.id, user.role, user.username)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "display_name": user.display_name or user.username,
            "theme": user.theme or "",
        },
    }


class ThemeUpdate(BaseModel):
    theme: str  # 'light' | 'dark'


@router.get("/theme")
def get_theme(request: Request):
    """获取用户主题偏好"""
    db = get_db()
    uid = getattr(request.state, 'user_id', None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    return {"theme": db.get_user_theme(uid)}


@router.put("/theme")
def update_theme(req: ThemeUpdate, request: Request):
    """更新用户主题偏好"""
    if req.theme not in ('light', 'dark'):
        raise HTTPException(status_code=400, detail="theme 必须为 light 或 dark")
    uid = getattr(request.state, 'user_id', None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    db = get_db()
    ok = db.update_user_theme(uid, req.theme)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True, "theme": req.theme}


class ProfileUpdate(BaseModel):
    display_name: str = ""


class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str


@router.put("/profile")
def update_profile(req: ProfileUpdate, request: Request):
    """更新个人信息（显示名称）"""
    uid = getattr(request.state, 'user_id', None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    if not req.display_name.strip():
        raise HTTPException(status_code=400, detail="显示名称不能为空")
    db = get_db()
    ok = db.update_display_name(uid, req.display_name.strip())
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True, "display_name": req.display_name.strip()}


@router.put("/password")
def update_password(req: PasswordUpdate, request: Request):
    """修改密码"""
    uid = getattr(request.state, 'user_id', None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    db = get_db()
    ok, err = db.change_password(uid, req.old_password, req.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"ok": True}


class AgentModelUpdate(BaseModel):
    role: str       # orchestrator, analysis, collection, automation, audit
    model_id: str   # 分配给该角色的模型 ID


@router.get("/agent-models")
def get_agent_models(request: Request):
    """获取 Agent 角色 → 模型分配"""
    from config.settings import AGENT_MODEL_MAP
    # 优先读取 models.json 中的自定义分配
    custom = _read_agent_models()
    merged = dict(AGENT_MODEL_MAP)
    merged.update(custom)
    return {"agent_models": merged}


@router.put("/agent-models")
def update_agent_models(req: AgentModelUpdate, request: Request):
    """更新 Agent 角色 → 模型分配"""
    from config.settings import AGENT_MODEL_MAP
    valid_roles = list(AGENT_MODEL_MAP.keys())
    if req.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"无效角色: {req.role}，可选: {valid_roles}")
    data = _read_models_file()
    agent_models = data.get("_agent_models", {})
    agent_models[req.role] = req.model_id
    data["_agent_models"] = agent_models
    _write_models_file(data)
    return {"ok": True, "role": req.role, "model_id": req.model_id}


class ApiKeyBody(BaseModel):
    provider: str
    key: str


@router.get("/apikeys")
def get_apikeys(request: Request):
    """获取已配置的 API Key（密钥脱敏）"""
    data = _read_models_file()
    keys = data.get("_apikeys", {})
    masked = {}
    for k, v in keys.items():
        masked[k] = v[:4] + "****" + v[-4:] if len(v) > 8 else "****"
    return {"keys": masked}


@router.post("/apikeys")
def save_apikey(req: ApiKeyBody, request: Request):
    """保存 API Key"""
    data = _read_models_file()
    keys = data.get("_apikeys", {})
    keys[req.provider] = req.key
    data["_apikeys"] = keys
    _write_models_file(data)
    return {"ok": True, "provider": req.provider}


@router.delete("/apikeys")
def delete_apikey(req: ApiKeyBody, request: Request):
    """删除 API Key"""
    data = _read_models_file()
    keys = data.get("_apikeys", {})
    keys.pop(req.provider, None)
    if keys:
        data["_apikeys"] = keys
    else:
        data.pop("_apikeys", None)
    _write_models_file(data)
    return {"ok": True}


class TokenCheck(BaseModel):
    token: str


@router.post("/check")
def check_token(req: TokenCheck):
    """验证 token 是否有效"""
    payload = verify_token(req.token)
    if not payload:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    db = get_db()
    user = db.get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user.frozen_until and user.frozen_until > datetime.utcnow():
        return {"valid": False, "detail": "账号已被冻结"}
    if user.locked_until and user.locked_until > datetime.utcnow():
        return {"valid": False, "detail": "账号已被临时锁定"}
    return {
        "valid": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "display_name": user.display_name or user.username,
            "theme": user.theme or "",
        },
    }
