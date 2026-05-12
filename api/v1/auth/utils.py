import secrets
import time
from datetime import datetime, timedelta
from jose import jwt, JWTError
from config.settings import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_DAYS


def create_token(user_id: int, role: str = "user", username: str = "") -> str:
    expire = datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS)
    payload = {"user_id": user_id, "role": role, "username": username, "exp": expire}
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
