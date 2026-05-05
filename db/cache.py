import json
from db.redis_client import get_redis

_TASK_STATE_KEY = "browser:task_state"
_BROWSER_STATUS_KEY = "browser:status"


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
