import os
import redis

pool = redis.ConnectionPool(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=int(os.getenv("REDIS_DB", "0")),
    # S2.2：requirepass（.env 的 REDIS_PASSWORD；未设置时兼容本地裸 Redis）
    password=os.getenv("REDIS_PASSWORD") or None,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=3,  # 2026-10-19：此前无读超时——Redis 卡死时调用挂起，所有故障降级不触发
)


def get_redis():
    return redis.Redis(connection_pool=pool)
