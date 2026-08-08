TOOL_CATEGORY = "memory"

"""用户记忆工具"""
from langchain_core.tools import tool
from yuanai_core.rag import current_user_id


@tool
def get_user_memory(query: str = "") -> str:
    """Retrieve stored user info. query: optional filter keyword."""
    from db.session import get_db
    db = get_db()
    uid = current_user_id()
    memory = db.get_user_memory(uid)
    if not memory:
        return "暂无用户记忆"
    if query:
        lines = [l for l in memory.split('\n') if query.lower() in l.lower()]
        return '\n'.join(lines) if lines else f"记忆中没有匹配 '{query}' 的内容"
    return memory


@tool
def remember_user_info(info: str) -> str:
    """Append user info to memory. info: fact to remember (appended, not overwritten)."""
    from db.session import get_db
    db = get_db()
    uid = current_user_id()
    existing = db.get_user_memory(uid) or ""
    if existing and info.strip() in existing:
        return "已存在相同记忆，无需重复保存"
    merged = (existing + "\n" + info.strip()).strip() if existing.strip() else info.strip()
    ok = db.update_user_memory(uid, merged)
    return "记忆已保存" if ok else "保存失败"
