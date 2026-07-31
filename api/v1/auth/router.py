import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator
from db.session import get_db
from api.v1.auth.utils import create_token, verify_token
from api.v1.ratelimit import auth_limiter, get_client_ip

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

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
