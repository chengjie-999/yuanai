import time
import logging
from collections import defaultdict
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from db.session import get_db
from api.v1.auth.utils import create_token, verify_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# 登录速率限制：每个 IP 5 次/分钟
_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_WINDOW = 60
_LOGIN_MAX_ATTEMPTS = 5


def _check_login_rate(ip: str):
    now = time.time()
    attempts = _login_attempts[ip]
    attempts[:] = [t for t in attempts if now - t < _LOGIN_WINDOW]
    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="登录请求过于频繁，请 1 分钟后重试")
    attempts.append(now)


class AuthRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(AuthRequest):
    display_name: str = ""
    role: str = "user"


@router.post("/register")
def register(req: RegisterRequest):
    """注册新用户"""
    raise HTTPException(status_code=403, detail="注册功能暂不开放，请联系管理员创建账号")


@router.post("/login")
def login(req: AuthRequest, request: Request):
    """用户登录"""
    ip = request.client.host if request.client else "unknown"
    _check_login_rate(ip)
    db = get_db()
    user = db.authenticate_user(req.username, req.password)
    if not user:
        logger.warning("登录失败: username=%s, ip=%s", req.username, ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if user.frozen_until and user.frozen_until > datetime.utcnow():
        days = (user.frozen_until - datetime.utcnow()).days
        raise HTTPException(status_code=403, detail=f"账号已被冻结，剩余 {days} 天")
    token = create_token(user.id, user.role, user.username)
    return {
        "token": token,
        "user": {"id": user.id, "username": user.username, "role": user.role, "display_name": user.display_name or user.username},
    }


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
    return {
        "valid": True,
        "user": {"id": user.id, "username": user.username, "role": user.role, "display_name": user.display_name or user.username},
    }
