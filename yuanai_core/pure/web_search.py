"""网页搜索纯函数 — DuckDuckGo HTML 端点（免费无 Key），结果供 fetch_url/parse_html 接力

与数据采集链路融合：search_web 给 URL → 模型用 fetch_url + parse_html 取详情。
请求走 safe_fetch（SSRF 守卫 + 超时 + 体积上限，与 fetch_url 同一条咽喉）。
"""
import re
from typing import List, Dict

SEARCH_BASE = "https://html.duckduckgo.com/html/"
SEARCH_TIMEOUT_S = 10
SEARCH_MAX_RESULTS = 5


def _clean_text(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def _fetch(url: str, params: dict):
    from spiderlx.core.requests.safe_fetch import safe_get
    return safe_get(
        url,
        params=params,
        timeout=SEARCH_TIMEOUT_S,
        headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        },
        max_bytes=1024 * 1024,
    )


def _search_ddg(q: str, max_results: int) -> List[Dict]:
    """DuckDuckGo HTML 端点（国内可能不通 → 调用方回退 Bing）"""
    from bs4 import BeautifulSoup

    result = _fetch(SEARCH_BASE, {"q": q})
    soup = BeautifulSoup(result.text, "html.parser")
    out = []
    # 结果链接：a.result__a（href 形如 //duckduckgo.com/l/?uddg=<url>）
    for a in soup.select("a.result__a"):
        title = _clean_text(a.get_text())
        href = a.get("href") or ""
        m = re.search(r"[?&]uddg=([^&]+)", href)
        url = m.group(1) if m else href
        from urllib.parse import unquote
        try:
            url = unquote(url)
        except Exception:
            pass
        if not title or not url.startswith("http"):
            continue
        snippet = ""
        snip = a.find_next("a", class_="result__snippet")
        if snip:
            snippet = _clean_text(snip.get_text())
        out.append({"title": title[:120], "url": url[:300], "snippet": snippet[:300]})
        if len(out) >= max_results:
            break
    return out


def _search_bing(q: str, max_results: int) -> List[Dict]:
    """Bing 国内站（cn.bing.com，境内可用）→ 结果解析"""
    from bs4 import BeautifulSoup

    result = _fetch("https://cn.bing.com/search", {"q": q})
    soup = BeautifulSoup(result.text, "html.parser")
    out = []
    for li in soup.select("li.b_algo"):
        a = li.select_one("h2 a")
        if not a:
            continue
        title = _clean_text(a.get_text())
        url = a.get("href") or ""
        if not title or not url.startswith("http"):
            continue
        cap = li.select_one("div.b_caption p") or li.select_one("p")
        snippet = _clean_text(cap.get_text()) if cap else ""
        out.append({"title": title[:120], "url": url[:300], "snippet": snippet[:300]})
        if len(out) >= max_results:
            break
    return out


def web_search(query: str, max_results: int = SEARCH_MAX_RESULTS) -> List[Dict]:
    """网页搜索（DDG 优先，失败/空结果回退 Bing）→ [{title, url, snippet}]"""
    q = (query or "").strip()
    if not q:
        return []
    for searcher in (_search_ddg, _search_bing):
        try:
            results = searcher(q, max_results)
            if results:
                return results
        except Exception:
            continue
    return []


def format_search_results(results: List[Dict]) -> str:
    """结果 → 模型可读文本（供工具返回与上下文拼接）"""
    if not results:
        return "未找到相关结果（搜索服务暂不可用或结果为空）"
    lines = [f"共 {len(results)} 条结果:"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}")
    return "\n".join(lines)
