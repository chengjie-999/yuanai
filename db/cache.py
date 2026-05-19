import json
from db.redis_client import get_redis

_CHAT_MSG_KEY = "chat:messages:"  # + session_id


# ---- 聊天消息缓存 ----

def cache_chat_messages(session_id: str, messages: list):
    """缓存聊天消息到 Redis（1小时过期）"""
    try:
        r = get_redis()
        key = _CHAT_MSG_KEY + session_id
        r.setex(key, 3600, json.dumps(messages, ensure_ascii=False))
    except Exception:
        pass


def get_cached_chat_messages(session_id: str) -> list:
    """从 Redis 获取缓存的聊天消息"""
    try:
        r = get_redis()
        key = _CHAT_MSG_KEY + session_id
        data = r.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception:
        return None


def clear_chat_cache(session_id: str):
    """清除某会话的缓存"""
    try:
        get_redis().delete(_CHAT_MSG_KEY + session_id)
    except Exception:
        pass
