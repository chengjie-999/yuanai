from fastapi import Request, HTTPException
from starlette.responses import JSONResponse
from api.v1.auth.utils import verify_token

# 不需要鉴权的路径前缀
PUBLIC_PATHS = ["/", "/health", "/api/v1/auth", "/api/v1/qimg", "/api/v1/monitor", "/api/v1/browser/stream"]


def is_public(path: str) -> bool:
    for p in PUBLIC_PATHS:
        if path == p or path.startswith(p + "/") or path.startswith(p + "?"):
            return True
    return False


async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # 公开路径放行
    if is_public(path):
        return await call_next(request)

    # 取 Authorization header
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "未提供 token"})

    token = auth[7:]
    payload = verify_token(token)
    if not payload:
        return JSONResponse(status_code=401, content={"detail": "token 无效或已过期"})

    # 注入用户信息到 request.state
    request.state.user_id = payload["user_id"]
    request.state.role = payload["role"]
    request.state.username = payload.get("username", "")

    return await call_next(request)


def require_admin(request: Request):
    """检查当前用户是否为 admin，否则抛 403"""
    role = getattr(request.state, "role", "")
    if role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
