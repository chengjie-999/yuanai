TOOL_CATEGORY = "memory"

"""用户记忆工具 — 双路径读写 data/.yuan/（云端进程直连 / 本地 Agent 走 HTTP）

- 云端进程（统筹/子 Agent/折叠/云端直连 LLM）：本机就有 MySQL + 文件
  存储，直连 DB 层（db 方法已委托 memory_store 文件存储），无凭据问题
- 本地 Agent 进程（用户电脑，无云端 DB）：经 /api/v1/agent/memory
  HTTP（agent 凭据）由云端进程落盘
判定：优先尝试直连，DB 不可达（连接异常）时回退 HTTP。
"""
import json
import logging
import urllib.request

from langchain_core.tools import tool
from yuanai_core.rag import current_user_id

logger = logging.getLogger(__name__)


def _agent_http(path: str, method: str = "GET", payload: dict = None) -> dict:
    """本地 Agent → 云端 /agent/memory 调用（凭据来自 data/agent_identity.json）"""
    import os

    from utils.data_path import root_path

    identity = {}
    try:
        with open(os.path.join(root_path(), "data", "agent_identity.json"), encoding="utf-8") as f:
            identity = json.load(f)
    except OSError:
        pass
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
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8", errors="replace")).get("detail", "")
        except Exception:
            pass
        logger.warning("agent memory HTTP %s %s 失败(%s): %s", method, url, e.code, detail)
        return {"ok": False, "detail": detail or f"HTTP {e.code}（{server}）"}
    except Exception as e:
        logger.warning("agent memory HTTP %s 异常: %s", method, e)
        return {"ok": False, "detail": f"{e}（{server}）"}


def _memory_ops():
    """记忆读写入口：云端进程直连（DB 层 → data/.yuan/ 文件），DB 不可达返回 None"""
    from db.session import get_db

    db = get_db()  # 本地 Agent 无云端 DB 时此处抛异常，调用方回退 HTTP
    return db


def _call_memory(path: str, method: str = "GET", payload: dict = None,
                 uid: int = 0) -> dict:
    """双路径：直连优先（云端），失败回退 HTTP（本地 Agent）"""
    try:
        db = _memory_ops()
    except Exception as e:
        logger.info("记忆直连不可用（本地 Agent），回退 HTTP: %s", type(e).__name__)
        return _agent_http(path, method, payload)

    from yuanai_core.memory import _is_placeholder

    if method == "GET":
        return {"ok": True, "memory": db.get_user_memory(uid)}
    if method == "POST":
        from config.settings import MEMORY_MAX_ITEMS, MEMORY_MAX_CHARS
        facts = [str(f)[:200] for f in (payload or {}).get("facts", [])
                 if str(f).strip() and not _is_placeholder(str(f))]
        if not facts:
            return {"ok": True, "added": 0}
        r = db.merge_user_memory(uid, facts, MEMORY_MAX_ITEMS, MEMORY_MAX_CHARS)
        return {"ok": True, "added": r["added"]}
    if method == "DELETE":
        r = db.delete_user_memory_line(uid, (payload or {}).get("line", "").strip())
        if r["asked_more"]:
            return {"ok": False, "detail": "匹配到多条记忆，请说得更具体"}
        return {"ok": True, "deleted": r["deleted"], "memory": r["memory"]}
    return {"ok": False, "detail": f"不支持的方法 {method}"}


@tool
def get_user_memory(query: str = "") -> str:
    """Retrieve stored user info. query: optional filter keyword."""
    from yuanai_core.memory import _is_placeholder
    uid = current_user_id.get()
    r = _call_memory("/memory", "GET", uid=uid)
    if not r.get("ok"):
        return f"读取用户记忆失败：{r.get('detail', '未知错误')}"
    memory = r.get("memory") or ""
    if not memory:
        return "暂无用户记忆"
    if query and not _is_placeholder(query):
        lines = [l for l in memory.split('\n') if query.lower() in l.lower()]
        return '\n'.join(lines) if lines else f"记忆中没有匹配 '{query}' 的内容"
    return memory


@tool
def remember_user_info(info: str) -> str:
    """Append user info to memory. info: fact to remember (appended, not overwritten)."""
    from yuanai_core.memory import _is_placeholder
    fact = (info or "").strip()
    if not fact or _is_placeholder(fact):
        return "这句话没有可保存的信息"
    uid = current_user_id.get()
    r = _call_memory("/memory", "POST", {"user_id": uid, "facts": [fact]}, uid=uid)
    if not r.get("ok"):
        return f"保存记忆失败：{r.get('detail', '未知错误')}"
    if r.get("added", 0) == 0:
        return "已存在相同记忆，无需重复保存"
    return "记忆已保存"


@tool
def forget_user_info(info: str) -> str:
    """Delete a stored user fact. info: the fact text (or a unique keyword in it)."""
    kw = (info or "").strip()
    if not kw:
        return "请说明要忘记什么"
    uid = current_user_id.get()
    r = _call_memory("/memory", "DELETE", {"user_id": uid, "line": kw}, uid=uid)
    if not r.get("ok"):
        detail = r.get("detail") or ""
        if "多条" in str(detail):
            return "这条内容匹配到多条记忆，请说得更具体"
        return f"删除记忆失败：{detail or '未知错误'}"
    if r.get("deleted", 0) == 0:
        return "记忆中没有找到这条内容"
    return "已忘记这条记忆"
