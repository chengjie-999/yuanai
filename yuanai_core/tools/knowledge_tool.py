"""知识库检索工具 — 自动接入 AI Agent，支持私有/共享隔离"""
from langchain_core.tools import tool
from yuanai_core.rag import search_knowledge, list_knowledge_sources, current_user_id


@tool
def retrieve_knowledge(query: str) -> str:
    """
    从知识库中检索相关内容。当用户询问任何知识性问题时调用此工具。
    输入：自然语言查询（如 'Python for 循环的用法'）
    输出：知识库中语义最相关的段落及路径（自动包含共享知识 + 当前用户的私有知识）。
    """
    if not query:
        return "当前知识库包含以下来源：" + ", ".join(list_knowledge_sources())
    uid = current_user_id.get()
    return search_knowledge(query, user_id=uid if uid else None)
