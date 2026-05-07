import json
from db.redis_client import get_redis

_TASK_STATE_KEY = "browser:task_state"
_BROWSER_STATUS_KEY = "browser:status"
_CHAT_MSG_KEY = "chat:messages:"  # + session_id


def get_task_state() -> dict:
    try:
        data = get_redis().get(_TASK_STATE_KEY)
        return json.loads(data) if data else {"step": 1, "taskStarted": False, "currentTaskName": ""}
    except Exception:
        return {"step": 1, "taskStarted": False, "currentTaskName": ""}


def set_task_state(data: dict):
    try:
        get_redis().setex(_TASK_STATE_KEY, 3600, json.dumps(data))
    except Exception:
        pass


def clear_task_state():
    try:
        get_redis().delete(_TASK_STATE_KEY)
    except Exception:
        pass


def get_browser_status() -> dict:
    try:
        data = get_redis().get(_BROWSER_STATUS_KEY)
        return json.loads(data) if data else {"running": False, "url": "", "title": ""}
    except Exception:
        return {"running": False, "url": "", "title": ""}


def set_browser_status(running: bool, url: str = "", title: str = ""):
    try:
        get_redis().setex(_BROWSER_STATUS_KEY, 30, json.dumps({
            "running": running, "url": url, "title": title,
        }))
    except Exception:
        pass


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
