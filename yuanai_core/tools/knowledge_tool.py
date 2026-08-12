TOOL_CATEGORY = "knowledge"

"""知识库检索工具"""
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def retrieve_knowledge(query: str) -> str:
    """Search knowledge base. query: keywords to search for."""
    try:
        from yuanai_core.rag import search_knowledge, list_knowledge_sources

        if not query.strip():
            try:
                sources = list_knowledge_sources()
            except Exception:
                sources = []
            return f"请提供搜索关键词。可用知识源: {', '.join(sources)}" if sources else "知识库为空"

        results = search_knowledge(query)
        return results if results else f"未找到与 '{query}' 相关的内容"
    except Exception as e:
        logger.error("知识库检索失败: %s", e, exc_info=True)
        return f"知识库检索暂时不可用: {e}"
