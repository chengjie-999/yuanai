"""
JWT 鉴权中间件。
公开路径：/、/health、/api/v1/auth/*、/api/v1/knowledge/img、/api/v1/analysis/rfm-chart
其他所有路径需要 Authorization: Bearer <token> 或 ?token=<token>
"""
import logging
from datetime import datetime
from fastapi import Request
from api.v1.auth.utils import verify_token, verify_sse_token
from api.v1.exceptions import Unauthorized, Forbidden

logger = logging.getLogger(__name__)

PUBLIC_PATHS = ["/", "/health", "/docs", "/openapi.json", "/api/v1/auth/login", "/api/v1/auth/check", "/api/v1/auth/register", "/api/v1/knowledge/img", "/api/v1/analysis/rfm-chart", "/api/v1/chat/image", "/api/v1/agent/register"]


def is_public(path: str) -> bool:
    for p in PUBLIC_PATHS:
        if path == p or path.startswith(p + "/") or path.startswith(p + "?"):
            return True
    return False


def _extract_token(request: Request) -> str:
    """从 Authorization header（优先）或 WebSocket query 参数提取 token"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    # WebSocket 升级请求无法携带 Authorization header，只能通过 query 参数
    if request.url.path.startswith("/api/v1/agent/ws"):
        return request.query_params.get("token", "")
    return ""


async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # Agent WebSocket 连接由端点自行鉴权（JWT 或 agent_secret），中间件直接放行
    if path.startswith("/api/v1/agent/ws"):
        return await call_next(request)

    if is_public(path):
        return await call_next(request)

    token = _extract_token(request)
    if not token:
        raise Unauthorized("未提供 token")

    payload = verify_token(token)
    if payload:
        request.state.user_id = payload["user_id"]
        request.state.role = payload["role"]
        request.state.username = payload.get("username", "")
    else:
        sse = verify_sse_token(token)
        if sse:
            request.state.user_id = sse[0]
            request.state.role = sse[1]
            request.state.username = ""
        else:
            raise Unauthorized("token 无效或已过期")

    # 冻结检查
    from db.session import get_db, User
    sess = None
    try:
        db = get_db()
        sess = db.Session()
        user = sess.query(User).filter_by(id=payload["user_id"]).first()
        if user and user.frozen_until and user.frozen_until > datetime.utcnow():
            raise Forbidden("账号已被冻结")
    except Exception:
        logger.exception("冻结检查时数据库异常")
    finally:
        if sess:
            sess.close()

    return await call_next(request)


async def rate_limit_middleware(request: Request, call_next):
    """API 全局限流中间件（在认证中间件之前执行）"""
    from api.v1.ratelimit import api_limiter, auth_limiter, upload_limiter, get_client_ip

    path = request.url.path

    # 跳过公开路径和非 API 路径
    if path in ("/", "/health", "/docs", "/openapi.json"):
        return await call_next(request)

    # 代码监控免限流（前端轮询频繁）
    if path.startswith("/api/v1/monitor"):
        return await call_next(request)

    ip = get_client_ip(request)

    # 登录/注册使用严格限流
    if path.startswith("/api/v1/auth/login") or path.startswith("/api/v1/auth/register"):
        auth_limiter.check(ip)
    # 上传端点使用中等限流
    elif path.startswith("/api/v1/data/upload"):
        upload_limiter.check(ip)
    # 其他 API 使用通用限流
    elif path.startswith("/api/"):
        api_limiter.check(ip)

    return await call_next(request)


def get_user_id(request: Request) -> int:
    """从 request.state 获取当前用户 ID，未认证返回 0"""
    return getattr(request.state, "user_id", 0)


def require_admin(request: Request):
    role = getattr(request.state, "role", "")
    if role != "admin":
        raise Forbidden("仅管理员可执行此操作")
