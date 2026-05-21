"""用户记忆工具 — AI 自主判断何时保存/读取用户个人信息"""
from langchain_core.tools import tool
from yuanai_core.rag import current_user_id


@tool
def remember_user_info(info: str) -> str:
    """
    保存/更新用户个人信息。**会替换全部记忆，不是追加**。
    使用流程：
    1. 先调用 get_user_memory 读取现有记忆
    2. 将新信息与旧信息合并去重，整理成完整列表
    3. 调用本工具一次性写入完整的合并文本
    输入：完整的用户信息文本（多行用换行分隔）
    输出：保存结果
    """
    if not info or not info.strip():
        return "未提供需要保存的信息"
    uid = current_user_id.get()
    if not uid:
        return "无法确定当前用户"
    from db.session import get_db
    ok = get_db().update_user_memory(uid, info.strip())
    return "已更新" if ok else "保存失败"


@tool
def get_user_memory(query: str = "") -> str:
    """
    获取之前保存的用户个人信息、偏好、背景。需要了解用户信息时调用。
    输入可为空（返回全部记忆），或输入关键词（返回相关信息）。
    输出：已保存的用户信息
    """
    uid = current_user_id.get()
    if not uid:
        return "无法确定当前用户"
    from db.session import get_db
    memory = get_db().get_user_memory(uid)
    if not memory:
        return "暂无该用户的记忆信息"
    if not query or not query.strip():
        return memory
    lines = memory.split("\n")
    matched = [l for l in lines if query.lower() in l.lower()]
    return "\n".join(matched) if matched else memory
