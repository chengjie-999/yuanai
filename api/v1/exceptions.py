"""统一异常层次 — 所有 API 错误通过 AppError 返回一致的结构"""

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """应用异常基类。status_code + internal_msg(日志) + user_msg(客户端)"""

    def __init__(self, status_code: int, user_msg: str, internal_msg: str = ""):
        self.status_code = status_code
        self.user_msg = user_msg
        self.internal_msg = internal_msg or user_msg


class Unauthorized(AppError):
    def __init__(self, msg: str = "未提供 token"):
        super().__init__(401, msg)


class Forbidden(AppError):
    def __init__(self, msg: str = "无权限"):
        super().__init__(403, msg)


class NotFound(AppError):
    def __init__(self, msg: str = "资源不存在"):
        super().__init__(404, msg)


class BadRequest(AppError):
    def __init__(self, msg: str = "请求参数错误"):
        super().__init__(400, msg)


class InternalError(AppError):
    def __init__(self, internal_msg: str = ""):
        super().__init__(500, "服务器内部错误", internal_msg)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """全局异常处理器：internal_msg 写日志，user_msg 返回客户端"""
    import logging
    logger = logging.getLogger("api.error")
    if exc.status_code >= 500:
        logger.error("内部错误: %s", exc.internal_msg, exc_info=True)
    else:
        logger.warning("客户端错误 %d: %s", exc.status_code, exc.internal_msg)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.user_msg})
