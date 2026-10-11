TOOL_CATEGORY = "memory"

"""用户记忆工具 — 读写云端 data/.yuan/ 文件（经 /api/v1/agent/memory，agent 凭据）

记忆文件只接受云端进程写入：本地 Agent 工具一律走 HTTP，不直连 DB。
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
        logger.warning("agent memory HTTP %s 失败(%s): %s", method, e.code, detail)
        return {"ok": False, "detail": detail or f"HTTP {e.code}"}
    except Exception as e:
        logger.warning("agent memory HTTP %s 异常: %s", method, e)
        return {"ok": False, "detail": str(e)}


@tool
def get_user_memory(query: str = "") -> str:
    """Retrieve stored user info. query: optional filter keyword."""
    from yuanai_core.memory import _is_placeholder
    uid = current_user_id.get()
    r = _agent_http(f"/memory?user_id={uid}", "GET")
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
    r = _agent_http("/memory", "POST", {"user_id": uid, "facts": [fact]})
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
    r = _agent_http("/memory", "DELETE", {"user_id": uid, "line": kw})
    if not r.get("ok"):
        detail = r.get("detail") or ""
        if "多条" in str(detail):
            return "这条内容匹配到多条记忆，请说得更具体"
        return f"删除记忆失败：{detail or '未知错误'}"
    if r.get("deleted", 0) == 0:
        return "记忆中没有找到这条内容"
    return "已忘记这条记忆"
