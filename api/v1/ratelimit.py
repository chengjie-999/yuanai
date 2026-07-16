"""
API 全局限流模块 — 基于 Redis + 内存降级

用法：
  from api.v1.ratelimit import RateLimiter

  # 默认：每 IP 每 60s 最多 60 次
  limiter = RateLimiter("api", max_requests=60, window=60)

  # 在路由中：
  @router.get("/xxx")
  def handler(request: Request):
      limiter.check(request)  # 超限抛出 AppError(429)
      ...
"""

import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimiter:
    """Redis 优先、内存降级的速率限制器"""

    def __init__(self, name: str, max_requests: int = 60, window: int = 60):
        """
        Args:
            name: 限流规则名称（用于 Redis key 前缀）
            max_requests: 时间窗口内最大请求数
            window: 时间窗口（秒）
        """
        self.name = name
        self.max_requests = max_requests
        self.window = window
        self._fallback: dict[str, list[float]] = defaultdict(list)

    def _redis_key(self, identifier: str) -> str:
        return f"ratelimit:{self.name}:{identifier}"

    def check(self, identifier: str) -> None:
        """
        检查是否超限，超限抛出 AppError(429)。

        Args:
            identifier: 限流标识（通常为 IP 地址）
        """
        from api.v1.exceptions import AppError
        now = time.time()
        try:
            from db.redis_client import get_redis
            rds = get_redis()
            key = self._redis_key(identifier)
            count = rds.incr(key)
            if count == 1:
                rds.expire(key, self.window)
            if count > self.max_requests:
                raise AppError(
                    429,
                    f"请求过于频繁，请 {self.window} 秒后重试（{self.max_requests}次/{self.window}秒）",
                )
        except AppError:
            raise
        except Exception:
            # Redis 不可用时退回到进程内存（不跨实例共享）
            self._check_fallback(identifier, now)

    def _check_fallback(self, identifier: str, now: float) -> None:
        from api.v1.exceptions import AppError
        attempts = self._fallback[identifier]
        # 清理过期记录
        attempts[:] = [t for t in attempts if now - t < self.window]
        if len(attempts) >= self.max_requests:
            raise AppError(
                429,
                f"请求过于频繁，请 {self.window} 秒后重试",
            )
        attempts.append(now)
        # 定期清理过期 key 防止内存泄漏
        if len(self._fallback) > 10000:
            self._cleanup_fallback(now)

    def _cleanup_fallback(self, now: float) -> None:
        """清理过期的内存 fallback 记录"""
        expired = [
            k for k, v in self._fallback.items()
            if not any(now - t < self.window for t in v)
        ]
        for k in expired:
            del self._fallback[k]


# ===================== 预置限流器 =====================

# 通用 API（60次/60秒）
api_limiter = RateLimiter("api", max_requests=60, window=60)

# 登录/注册等敏感操作（5次/60秒）
auth_limiter = RateLimiter("auth", max_requests=5, window=60)

# 文件上传（10次/60秒）
upload_limiter = RateLimiter("upload", max_requests=10, window=60)


def get_client_ip(request) -> str:
    """从 Request 提取客户端 IP（优先 X-Forwarded-For）"""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # Starlette/FastAPI Request
    if hasattr(request, "client") and request.client:
        return request.client.host
    return "127.0.0.1"
