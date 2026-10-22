TOOL_CATEGORY = "knowledge"

"""知识库检索工具 — 双路径（与 user_memory 同款判定）

- 云端进程/本地联调：直连本机 Milvus（yuanai_core.rag.search_knowledge）
- 部署 Agent（用户电脑无 Milvus）：经 /api/v1/agent/knowledge/search HTTP
  由云端执行——曾直连本机 Milvus（连接重试挂死，卡对话 120s，2026-10-22 修复）
"""
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def retrieve_knowledge(query: str) -> str:
    """Search knowledge base. query: keywords to search for."""
    try:
        from yuanai_core.rag import current_user_id
        from yuanai_core.tools._agent_remote import is_remote_agent, agent_http

        try:
            uid = current_user_id.get()
        except Exception:
            uid = 0

        if not query.strip():
            if is_remote_agent():
                return "请提供搜索关键词"
            try:
                from yuanai_core.rag import list_knowledge_sources
                sources = list_knowledge_sources()
            except Exception:
                sources = []
            return f"请提供搜索关键词。可用知识源: {', '.join(sources)}" if sources else "知识库为空"

        if is_remote_agent():
            # 部署 Agent：云端执行检索（知识库在云端，用户隔离由设备绑定推导）
            r = agent_http("/knowledge/search", "POST",
                           {"query": query, "user_id": uid, "top_k": 5}, timeout=30)
            if r.get("ok"):
                text = r.get("text") or ""
                return text if text else f"未找到与 '{query}' 相关的内容"
            return f"知识库检索暂时不可用: {r.get('detail', '')}"

        # 云端进程/本地联调：直连本机 Milvus（传当前请求上下文用户，闭合跨用户泄漏）
        from yuanai_core.rag import search_knowledge
        results = search_knowledge(query, user_id=uid)
        return results if results else f"未找到与 '{query}' 相关的内容"
    except Exception as e:
        logger.error("知识库检索失败: %s", e, exc_info=True)
        return f"知识库检索暂时不可用: {e}"
