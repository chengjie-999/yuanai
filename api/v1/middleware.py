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

PUBLIC_PATHS = ["/", "/health", "/docs", "/openapi.json", "/api/v1/auth/login", "/api/v1/auth/check", "/api/v1/auth/register", "/api/v1/knowledge/img", "/api/v1/analysis/rfm-chart", "/api/v1/chat/image", "/api/v1/agent/register", "/api/v1/stats/visit"]


def is_public(path: str) -> bool:
    for p in PUBLIC_PATHS:
        if path == p or path.startswith(p + "/") or path.startswith(p + "?"):
            return True
    return False


def _extract_token(request: Request) -> str:
    """从 Authorization header（优先）或 query 参数提取 token。
    query token 仅对无法携带 header 的场景开放：WebSocket 升级、iframe 加载的图表资源。"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    path = request.url.path
    # WebSocket 升级请求无法携带 Authorization header，只能通过 query 参数
    # iframe src 同理（MessageBubble/AnalysisResultView/大屏的 plotly 图表）
    # 知识星球笔记图片/导图原文件同理（<img>/<iframe> 带不上 header，走 ?token=）
    if path.startswith("/api/v1/agent/ws") or path.startswith("/api/v1/data/script-html") \
            or path.startswith("/api/v1/data/analysis-html") \
            or path.startswith("/api/v1/planet/asset") \
            or path.startswith("/api/v1/admin/file-html") \
            or path.startswith("/api/v1/admin/file-media") \
            or (path.startswith("/api/v1/planet/maps") and path.endswith("/origin")):
        return request.query_params.get("token", "")
    return ""


async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # Agent WebSocket 连接与 vault 同步 REST 由端点自行鉴权
    #（JWT 或 agent_secret / X-Agent-Id+Secret），中间件直接放行
    if (path.startswith("/api/v1/agent/ws") or path.startswith("/api/v1/agent/planet")
            or path.startswith("/api/v1/agent/bridge-memory")
            or path.startswith("/api/v1/agent/memory")):
        return await call_next(request)

    if is_public(path):
        return await call_next(request)

    # 注意：ASGI 中间件里 raise AppError 不会被 FastAPI 异常处理器接管
    #（ServerErrorMiddleware 对非 HTTPException 一律 500），必须直接返回 JSONResponse
    from fastapi.responses import JSONResponse

    token = _extract_token(request)
    if not token:
        return JSONResponse(status_code=401, content={"detail": "未提供 token"})

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
            return JSONResponse(status_code=401, content={"detail": "token 无效或已过期"})

    # 冻结检查（S1.2 修复：sse token 分支 payload 为 None，原来在此抛 TypeError 被
    # except 吞掉 → 冻结检查失效；统一改读 request.state.user_id）
    # S3.4：JWT 吊销——payload.tv 快照落后于用户 token_version 即 401
    #（老 token 无 tv 视作 0；sse 短期令牌跳过该检查）
    from db.session import get_db, User
    sess = None
    try:
        db = get_db()
        sess = db.Session()
        user = sess.query(User).filter_by(id=request.state.user_id).first()
        if user and user.frozen_until and user.frozen_until > datetime.utcnow():
            return JSONResponse(status_code=403, content={"detail": "账号已被冻结"})
        if payload and user and user.token_version and int(payload.get("tv") or 0) < user.token_version:
            return JSONResponse(status_code=401, content={"detail": "token 已失效，请重新登录"})
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

    # 后台管理免通用限流（JWT+admin 双重保护；仪表盘/分析页 15s 轮询频繁，
    # 60 次/分会把正常使用打爆 429）
    if path.startswith("/api/v1/admin/"):
        return await call_next(request)

    ip = get_client_ip(request)

    # 中间件里 raise AppError 不会被 FastAPI 异常处理器接管，必须直接返回 429 响应
    from fastapi.responses import JSONResponse
    from api.v1.exceptions import AppError
    try:
        # 登录/注册使用严格限流（S3.5：安装码注册端点同档——防枚举爆破）
        if path.startswith("/api/v1/auth/login") or path.startswith("/api/v1/auth/register") \
                or path.startswith("/api/v1/agent/register"):
            auth_limiter.check(ip)
        # 上传端点使用中等限流
        elif path.startswith("/api/v1/data/upload"):
            upload_limiter.check(ip)
        # 其他 API 使用通用限流
        elif path.startswith("/api/"):
            api_limiter.check(ip)
    except AppError as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.user_msg})

    return await call_next(request)


def get_user_id(request: Request) -> int:
    """从 request.state 获取当前用户 ID，未认证返回 0"""
    return getattr(request.state, "user_id", 0)


def require_admin(request: Request):
    role = getattr(request.state, "role", "")
    if role != "admin":
        raise Forbidden("仅管理员可执行此操作")
