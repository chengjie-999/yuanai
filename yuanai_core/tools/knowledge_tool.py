"""知识库检索工具 — 自动接入 AI Agent"""
from langchain_core.tools import tool
from yuanai_core.rag import search_knowledge, list_knowledge_sources


@tool
def retrieve_knowledge(query: str) -> str:
    """
    从知识库中检索相关内容。当用户询问任何知识性问题时调用此工具。
    输入：自然语言查询（如 'Python for 循环的用法'）
    输出：知识库中语义最相关的段落及路径。
    注意：需要先 build_knowledge_base() 才能检索。
    """
    if not query:
        return "当前知识库包含以下来源：" + ", ".join(list_knowledge_sources())
    return search_knowledge(query)
