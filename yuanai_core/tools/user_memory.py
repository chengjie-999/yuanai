"""用户记忆工具 — AI 自主判断何时保存/读取用户个人信息"""
from langchain_core.tools import tool
from yuanai_core.rag import current_user_id


@tool
def remember_user_info(info: str) -> str:
    """
    记住用户个人信息、偏好、背景。当用户主动告知个人信息时调用（如"我叫张三"、"我是Python初学者"、"我讨厌饼图"）。
    输入：需要记住的信息片段（简短一句话概括）
    输出：保存结果
    """
    if not info or not info.strip():
        return "未提供需要保存的信息"
    uid = current_user_id.get()
    if not uid:
        return "无法确定当前用户"
    from db.session import get_db
    ok = get_db().update_user_memory(uid, info.strip())
    return "已记住" if ok else "保存失败"


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
