import secrets
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from config.settings import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_DAYS


def create_token(user_id: int, role: str = "user", username: str = "", expires_days: Optional[float] = None, tv: Optional[int] = None) -> str:
    """签发 JWT。expires_days 为空时使用全局默认有效期；供 Agent 桥接等场景签发长令牌。

    S3.4：带 jti（唯一标识）与 tv（token_version 快照，None 时查库取当前值；
    老 token 无 tv 视作 0，兼容不强制全站重登）。
    """
    days = expires_days if expires_days is not None else JWT_EXPIRE_DAYS
    expire = datetime.utcnow() + timedelta(days=days)
    if tv is None:
        try:
            from db.session import get_db, User
            sess = get_db().Session()
            try:
                u = sess.query(User).filter_by(id=user_id).first()
                tv = u.token_version if u else 0
            finally:
                sess.close()
        except Exception:
            tv = 0
    payload = {"user_id": user_id, "role": role, "username": username,
               "jti": uuid.uuid4().hex, "tv": tv, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


# ——— SSE 短期令牌（5秒有效，单次使用，避免 JWT 长期暴露在 URL）———

_sse_tokens: dict[str, tuple[int, str, float]] = {}


def create_sse_token(user_id: int, role: str) -> str:
    _cleanup_sse_tokens()
    token = secrets.token_urlsafe(16)
    _sse_tokens[token] = (user_id, role, time.time())
    return token


def verify_sse_token(token: str):
    _cleanup_sse_tokens()
    if token in _sse_tokens:
        uid, role, _ = _sse_tokens.pop(token)
        return uid, role
    return None


def _cleanup_sse_tokens():
    now = time.time()
    expired = [k for k, v in _sse_tokens.items() if now - v[2] > 5]
    for k in expired:
        _sse_tokens.pop(k, None)
