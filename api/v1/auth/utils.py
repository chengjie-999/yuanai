import secrets
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from config.settings import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_DAYS


def create_token(user_id: int, role: str = "user", username: str = "", expires_days: Optional[float] = None, tv: Optional[int] = None, track_session: bool = False) -> str:
    """签发 JWT。expires_days 为空时使用全局默认有效期；供 Agent 桥接等场景签发长令牌。

    S3.4：带 jti（唯一标识）与 tv（token_version 快照，None 时查库取当前值；
    老 token 无 tv 视作 0，兼容不强制全站重登）。
    track_session（2026-10-30）：登录签发时置 True → payload 带 sess 标记，
    middleware 据此做并发会话数校验（≤5 台，超限踢最旧）——Agent 桥接/
    长令牌不走该通道不受影响。
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
    if track_session:
        payload["sess"] = 1
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# ===================== 登录会话跟踪（2026-10-30：并发登录数上限，超限踢最旧） =====================
# Redis hash login_sessions:{uid}：field=jti, value=exp 时间戳。Redis 故障一律
# fail-open（不限流放行）——限流降级不影响可用性，与全局限流同策略。

_SESSION_KEY = "login_sessions:{uid}"
_SESSION_TTL = 8 * 24 * 3600  # 比 JWT 有效期（7 天）长一天，自然清理死会话


def _session_key(uid: int) -> str:
    return _SESSION_KEY.format(uid=uid)


def register_login_session(user_id: int, jti: str, exp_ts: float) -> Optional[str]:
    """登录时登记会话。超过 MAX_LOGIN_SESSIONS 踢最旧（返回被踢 jti，无则 None）。"""
    from config.settings import MAX_LOGIN_SESSIONS
    try:
        from db.redis_client import get_redis
        rds = get_redis()
        key = _session_key(user_id)
        now = time.time()
        # 清理过期 + 取最旧（exp 最小 = 最早登录）
        sessions = rds.hgetall(key)
        for k, v in sessions.items():
            try:
                if float(v) < now:
                    rds.hdel(key, k)
            except (TypeError, ValueError):
                rds.hdel(key, k)
        sessions = rds.hgetall(key)
        evicted = None
        if len(sessions) >= MAX_LOGIN_SESSIONS:
            evicted = min(sessions, key=lambda k: float(sessions[k] or 0))
            rds.hdel(key, evicted)
        rds.hset(key, jti, exp_ts)
        rds.expire(key, _SESSION_TTL)
        return evicted
    except Exception:
        return None


def is_login_session_valid(user_id: int, jti: str) -> bool:
    """middleware 校验：jti 在会话清单内（或清单不存在=存量 token 兼容）→ True。
    Redis 故障 fail-open。"""
    if not jti:
        return True
    try:
        from db.redis_client import get_redis
        rds = get_redis()
        key = _session_key(user_id)
        if not rds.exists(key):
            return True  # 尚未有登录会话登记（存量 token），放行
        return bool(rds.hexists(key, jti))
    except Exception:
        return True


def remove_login_session(user_id: int, jti: str) -> None:
    """登出时移除（预留：当前前端登出仅清本地 token，后端无登出端点）"""
    try:
        from db.redis_client import get_redis
        rds = get_redis()
        rds.hdel(_session_key(user_id), jti)
    except Exception:
        pass


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
