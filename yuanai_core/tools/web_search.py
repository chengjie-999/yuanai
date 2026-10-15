TOOL_CATEGORY = "general"

"""联网搜索工具 — 常规聊天联网（与数据采集链路融合：搜出 URL → fetch_url + parse_html 取详情）"""
from langchain_core.tools import tool


@tool
def search_web(query: str, max_results: int = 5) -> str:
    """Search the web for current information. query: search keywords (Chinese or English),
    max_results: 1-8 (default 5). Returns title/url/snippet list. For full content of a
    result, use fetch_url + parse_html with the returned url."""
    from yuanai_core.pure.web_search import web_search, format_search_results

    n = max(1, min(int(max_results or 5), 8))
    results = web_search(query, n)
    return format_search_results(results)
