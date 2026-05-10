"""
JWT 鉴权中间件。
公开路径：/、/health、/api/v1/qimg、/api/v1/auth/login、/api/v1/auth/check、/api/v1/auth/register
其他所有路径需要 Authorization: Bearer <token> 或 ?token=<token>
"""
import logging
from datetime import datetime
from fastapi import Request, HTTPException
from starlette.responses import JSONResponse
from api.v1.auth.utils import verify_token

logger = logging.getLogger(__name__)

PUBLIC_PATHS = ["/", "/health", "/docs", "/openapi.json", "/api/v1/qimg", "/api/v1/auth/login", "/api/v1/auth/check", "/api/v1/auth/register"]


def is_public(path: str) -> bool:
    for p in PUBLIC_PATHS:
        if path == p or path.startswith(p + "/") or path.startswith(p + "?"):
            return True
    return False


def _extract_token(request: Request) -> str:
    """从 Authorization header 或 query 参数中提取 token"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    token = request.query_params.get("token", "")
    if token:
        return token
    return ""


async def auth_middleware(request: Request, call_next):
    path = request.url.path

    if is_public(path):
        return await call_next(request)

    token = _extract_token(request)
    if not token:
        return JSONResponse(status_code=401, content={"detail": "未提供 token"})

    payload = verify_token(token)
    if not payload:
        return JSONResponse(status_code=401, content={"detail": "token 无效或已过期"})

    request.state.user_id = payload["user_id"]
    request.state.role = payload["role"]
    request.state.username = payload.get("username", "")

    # 冻结检查
    from db.session import get_db, User
    sess = None
    try:
        db = get_db()
        sess = db.Session()
        user = sess.query(User).filter_by(id=payload["user_id"]).first()
        if user and user.frozen_until and user.frozen_until > datetime.utcnow():
            return JSONResponse(status_code=403, content={"detail": "账号已被冻结"})
    except Exception:
        logger.exception("冻结检查时数据库异常")
    finally:
        if sess:
            sess.close()

    return await call_next(request)


def require_admin(request: Request):
    role = getattr(request.state, "role", "")
    if role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
