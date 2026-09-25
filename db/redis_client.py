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
)


def get_redis():
    return redis.Redis(connection_pool=pool)
