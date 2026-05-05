import redis

pool = redis.ConnectionPool(
    host='localhost', port=6379, db=0,
    decode_responses=True,
    socket_connect_timeout=2,
)


def get_redis():
    return redis.Redis(connection_pool=pool)
