"""Agent → 云端 HTTP 桥接（纯 stdlib，无框架依赖——usage.py 等底层模块可安全导入，
不触发 tools 包的重装载循环）

部署在用户电脑上的 Agent 进程没有云端 MySQL/Milvus/文件存储，记忆/计划/
知识检索/用量上传等操作必须经云端 /api/v1/agent/* HTTP（agent 凭据）由云端进程执行。
进程身份判定（2026-10-12 教训：按身份判定，不「试连」——试连会连到本机开发
MySQL/Milvus，数据写进本地库云端永远读不到）：
- 云端容器（APP_HOME / APP_ENV=production）→ 直连本机
- 本地 Agent：identity.server_url 指向远程云端 → HTTP；指向 localhost（联调）→ 直连
"""
import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

_LOCALHOST = ("ws://localhost", "ws://127.0.0.1",
              "http://localhost", "http://127.0.0.1")


def read_identity() -> dict:
    """读本机 Agent 身份（data/agent_identity.json）；无文件/解析失败返回 {}"""
    import os

    from utils.data_path import root_path

    try:
        with open(os.path.join(root_path(), "data", "agent_identity.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def is_remote_agent() -> bool:
    """部署在用户电脑上的 Agent（server_url 指向远程云端）→ True"""
    import os

    if os.getenv("APP_HOME") or os.getenv("APP_ENV") == "production":
        return False
    server = str(read_identity().get("server_url") or "").lower()
    return bool(server and not server.startswith(_LOCALHOST))


def agent_http(path: str, method: str = "GET", payload: dict = None,
               timeout: float = 15.0) -> dict:
    """本地 Agent → 云端 /api/v1/agent* 调用（凭据来自 data/agent_identity.json）。
    失败不抛，返回 {"ok": False, "detail": ...}。"""
    identity = read_identity()
    server = (identity.get("server_url") or "http://localhost:8000").replace("ws://", "http://").replace("wss://", "https://")
    url = server.rstrip("/") + "/api/v1/agent" + path
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={
                                     "Content-Type": "application/json",
                                     "X-Agent-Id": str(identity.get("agent_id", "")),
                                     "X-Agent-Secret": str(identity.get("agent_secret", "")),
                                 })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8", errors="replace")).get("detail", "")
        except Exception:
            pass
        logger.warning("agent HTTP %s %s 失败(%s): %s", method, url, e.code, detail)
        return {"ok": False, "detail": detail or f"HTTP {e.code}（{server}）"}
    except Exception as e:
        logger.warning("agent HTTP %s 异常: %s", method, e)
        return {"ok": False, "detail": f"{e}（{server}）"}
