TOOL_CATEGORY = "knowledge"

"""知识库检索工具"""
from langchain_core.tools import tool
from yuanai_core.rag import search_knowledge, list_knowledge_sources, current_user_id


@tool
def retrieve_knowledge(query: str) -> str:
    """Search knowledge base. query: keywords to search for."""
    if not query.strip():
        sources = list_knowledge_sources(current_user_id())
        return f"请提供搜索关键词。可用知识源: {', '.join(sources)}" if sources else "知识库为空"
    results = search_knowledge(query)
    return results if results else f"未找到与 '{query}' 相关的内容"
