TOOL_CATEGORY = "memory"

"""用户记忆工具 — 双路径读写 data/.yuan/（云端进程直连 / 本地 Agent 走 HTTP）

- 云端进程（统筹/子 Agent/折叠/云端直连 LLM）：本机就有 MySQL + 文件
  存储，直连 DB 层（db 方法已委托 memory_store 文件存储），无凭据问题
- 本地 Agent 进程（用户电脑，无云端 DB）：经 /api/v1/agent/memory
  HTTP（agent 凭据）由云端进程落盘
判定（2026-10-12 修复「部署后记忆失效」）：按进程身份，不再「试连」——
「试连」在用户电脑上会连到本机开发 MySQL，记忆写进本地库云端永远读不到：
- 云端容器（APP_HOME / APP_ENV=production）→ 直连
- 本地 Agent：identity.server_url 指向远程云端 → 强制 HTTP（GET/DELETE
  必须带 user_id）；指向 localhost（本地开发联调）→ 直连本机库（与本地
  API 同库，一致）
"""
import json
import logging
import urllib.request

from langchain_core.tools import tool
from yuanai_core.rag import current_user_id

logger = logging.getLogger(__name__)

_LOCALHOST = ("ws://localhost", "ws://127.0.0.1",
              "http://localhost", "http://127.0.0.1")


def _read_identity() -> dict:
    """读本机 Agent 身份（data/agent_identity.json）；无文件/解析失败返回 {}"""
    import os

    from utils.data_path import root_path

    try:
        with open(os.path.join(root_path(), "data", "agent_identity.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _memory_path() -> str:
    """记忆读写路径判定：'direct'（云端进程直连）或 'http'（本地 Agent 经云端）"""
    import os

    if os.getenv("APP_HOME") or os.getenv("APP_ENV") == "production":
        return "direct"
    server = str(_read_identity().get("server_url") or "").lower()
    if server and not server.startswith(_LOCALHOST):
        return "http"
    return "direct"


def _agent_http(path: str, method: str = "GET", payload: dict = None) -> dict:
    """本地 Agent → 云端 /agent/memory 调用（凭据来自 data/agent_identity.json）"""
    identity = _read_identity()
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
    """记忆读写入口：云端进程直连（DB 层 → data/.yuan/ 文件）；DB 不可达抛异常"""
    from db.session import get_db

    db = get_db()  # 仅在直连判定（云端容器/本地联调）下到达；异常由 _call_memory 捕获
    return db


def _call_memory(path: str, method: str = "GET", payload: dict = None,
                 uid: int = 0) -> dict:
    """双路径：云端进程直连；本地 Agent（远程云端）走 HTTP 且必须带 user_id"""
    if _memory_path() == "http":
        # 本地 Agent：uid 随请求走（GET 拼 query，POST/DELETE 进 body，
        # 云端端点按 user_id 定位目录——丢 uid 曾致 400「缺少 user_id」）
        if method == "GET":
            return _agent_http(f"{path}?user_id={uid}", "GET")
        payload = dict(payload or {})
        payload.setdefault("user_id", uid)
        return _agent_http(path, method, payload)

    try:
        db = _memory_ops()
    except Exception as e:
        # 直连判定下 DB 不可达（云端容器 MySQL 故障 / 本地联调 MySQL 未启动）：
        # 不回退 HTTP（容器里残留凭据无效），报错可见
        logger.warning("记忆直连不可用: %s", type(e).__name__)
        return {"ok": False, "detail": f"记忆直连不可用（{type(e).__name__}）"}

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


# ⚠ 安全事故教训（2026-10-11）：曾定义 forget_user_info 工具供 LLM 调用，
# 模型在一次对话中自主连续调用 20+ 次删除记忆条目——**删除类操作绝不允许
# 暴露为 LLM 可自动调用的工具**。删除记忆的唯一入口是设置页「我的记忆」卡
# （每行删除按钮 + 编辑抽屉），必须由用户有意识地操作。
# 后端 DELETE /auth/memory 与 /agent/memory 端点保留（设置页与 Agent 同步用）。
