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
import logging

from langchain_core.tools import tool
from yuanai_core.rag import current_user_id, current_session_id
from yuanai_core.tools._agent_remote import is_remote_agent, agent_http as _agent_http

logger = logging.getLogger(__name__)


def _memory_path() -> str:
    """记忆读写路径判定：'direct'（云端进程直连）或 'http'（本地 Agent 经云端）。
    保留原名供 plan_tools 复用；身份判定实现已收敛到 _agent_remote。"""
    return "http" if is_remote_agent() else "direct"


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
        http_method = "POST" if method == "ORGANIZE" else method  # ORGANIZE 落 HTTP POST
        return _agent_http(path, http_method, payload)

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
    if method == "ORGANIZE":
        return db.organize_user_memory(uid, (payload or {}).get("items", []),
                                       (payload or {}).get("session_id", ""))
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
def organize_user_memory(items: str) -> str:
    """整理用户长期记忆：把当前记忆合并去重、改写得更准确、补充新事实，
    输出整理后的完整清单，一行一条。清单里没有的旧记忆会被删除——
    硬限制：每天最多删 3 条，且只能删本会话内新增的记忆；删除更早的
    记忆无法执行（会报错），请告诉用户到设置页「我的记忆」手动操作。"""
    from yuanai_core.memory import _is_placeholder
    text = (items or "").strip()
    if not text or _is_placeholder(text):
        return "没有可整理的内容"
    uid = current_user_id.get()
    sid = current_session_id.get()
    r = _call_memory("/memory/organize", "ORGANIZE",
                     {"user_id": uid, "session_id": sid, "items": [text]}, uid=uid)
    if not r.get("ok"):
        return f"整理失败：{r.get('detail', '未知错误')}"
    return f"记忆已整理：删除 {r.get('deleted', 0)} 条，现存 {r.get('total', 0)} 条"


# ⚠ 安全事故教训（2026-10-11）：曾定义 forget_user_info 工具供 LLM 调用，
# 模型在一次对话中自主连续调用 20+ 次删除记忆条目——**删除类操作绝不允许
# 暴露为 LLM 可自动调用的工具**。删除记忆的唯一入口是设置页「我的记忆」卡
# （每行删除按钮 + 编辑抽屉），必须由用户有意识地操作。
# 后端 DELETE /auth/memory 与 /agent/memory 端点保留（设置页与 Agent 同步用）。
