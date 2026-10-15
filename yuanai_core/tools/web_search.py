TOOL_CATEGORY = "general"

"""联网搜索工具 — 常规聊天联网（与数据采集链路融合：搜出 URL → fetch_url + parse_html 取详情）"""
from langchain_core.tools import tool


@tool
def search_web(query: str, max_results: int = 8) -> str:
    """Search the web for current information. query: 搜索词——用用户问题的核心短语、
    词间加空格分词（不要截取单个字，也不要把整句口语原样传入），如用户问「最新的
    AI 大模型动态」→ query 写「AI 大模型 最新进展」。max_results: 1-8 (default 8).
    Returns title/link/domain/snippet list. For full content of a result, use fetch_url
    + parse_html with the returned url."""
    from yuanai_core.pure.web_search import web_search, format_search_results

    q = (query or "").strip()
    if len(q) < 4:
        return f"搜索词过短（{q!r}）：请用用户的完整问题作为 query 重新调用（不要截取单个字）"
    n = max(1, min(int(max_results or 8), 8))
    results = web_search(q, n)
    return format_search_results(results)
