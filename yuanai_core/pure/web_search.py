"""网页搜索纯函数 — Bing 国内站主用（境内可用），DuckDuckGo 海外兜底（免费无 Key）

与数据采集链路融合：search_web 给 URL → 模型用 fetch_url + parse_html 取详情。
请求走 safe_fetch（SSRF 守卫 + 超时 + 体积上限，与 fetch_url 同一条咽喉）。
业内常规对齐（2026-10-15）：来源域名标注、同域去重、摘要去日期前缀、答案卡。
"""
import os
import re
import json
from typing import List, Dict
from urllib.parse import unquote, urlparse

SEARCH_BASE = "https://html.duckduckgo.com/html/"
SEARCH_TIMEOUT_S = 10
SEARCH_MAX_RESULTS = 8

# 摘要日期前缀（如「2026年8月4日 · 」）——业内展示不显示搜索引擎注入的日期行
_DATE_PREFIX_RE = re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日\s*[·|｜]\s*")


def _clean_text(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def _domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


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
    """DuckDuckGo HTML 端点（国内不通 → 海外兜底）"""
    from bs4 import BeautifulSoup

    result = _fetch(SEARCH_BASE, {"q": q})
    soup = BeautifulSoup(result.text, "html.parser")
    out = []
    for a in soup.select("a.result__a"):
        title = _clean_text(a.get_text())
        href = a.get("href") or ""
        m = re.search(r"[?&]uddg=([^&]+)", href)
        url = m.group(1) if m else href
        try:
            url = unquote(url)
        except Exception:
            pass
        if not title or not url.startswith("http"):
            continue
        snippet = ""
        snip = a.find_next("a", class_="result__snippet")
        if snip:
            snippet = _DATE_PREFIX_RE.sub("", _clean_text(snip.get_text()))
        out.append({"title": title[:120], "url": url[:300], "snippet": snippet[:300]})
        if len(out) >= max_results:
            break
    return out


def _search_bing(q: str, max_results: int) -> List[Dict]:
    """Bing 国内站（cn.bing.com，境内主用）→ 结果 + 答案卡解析"""
    from bs4 import BeautifulSoup

    result = _fetch("https://cn.bing.com/search", {"q": q})
    soup = BeautifulSoup(result.text, "html.parser")
    out = []
    # 答案卡（业内「直接答案」框，尽力而为）
    ans = soup.select_one(".b_ans")
    if ans:
        ans_text = _clean_text(ans.get_text())
        if ans_text and len(ans_text) < 400:
            out.append({"title": "直接答案", "url": "", "snippet": ans_text[:300], "answer": True})
    for li in soup.select("li.b_algo"):
        a = li.select_one("h2 a")
        if not a:
            continue
        title = _clean_text(a.get_text())
        url = a.get("href") or ""
        if not title or not url.startswith("http"):
            continue
        cap = li.select_one("div.b_caption p") or li.select_one("p")
        snippet = _DATE_PREFIX_RE.sub("", _clean_text(cap.get_text())) if cap else ""
        out.append({"title": title[:120], "url": url[:300], "snippet": snippet[:300]})
        if len(out) >= max_results + 1:  # +1 给答案卡占位
            break
    return out


def _dedup_domains(results: List[Dict], keep: int) -> List[Dict]:
    """同域去重（业内常规：一页内同站只展示首条）"""
    seen = set()
    out = []
    for r in results:
        if r.get("answer"):
            out.append(r)
            continue
        d = _domain_of(r["url"])
        if d and d in seen:
            continue
        if d:
            seen.add(d)
        out.append(r)
        if len(out) >= keep:
            break
    return out


def _search_deepseek(q: str, max_results: int) -> List[Dict]:
    """DeepSeek 官方搜索 API（2026-10-17 上线）：POST /v1/tools/search。

    结构化结果（rerank_score/authority 权威评级/长摘要），自研 AI 原生索引，
    过滤 SEO 作弊/低质 AIGC。免费过渡期至 2026-11-01，之后 5 元/千次（成功才计费）。
    失败/超时/限流抛异常，由 web_search 降级链兜底。
    """
    import urllib.request
    from utils.sensitive_data import get_api_key

    key = os.getenv("DEEPSEEK_API_KEY") or ""
    if not key:
        try:
            key = get_api_key("dsllm") or ""
        except Exception:
            key = ""
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置")

    payload = json.dumps({"query": q[:128], "count": min(max_results, 20)},
                         ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/tools/search",
        data=payload, method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "yuanai-agent/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    results = data.get("results") or []
    # 搜索调用记账（2026-10-22）：免费过渡期后 5 元/千次成功计费（per_call 定价）
    try:
        from yuanai_core.usage import record_usage
        from yuanai_core.rag import current_user_id
        record_usage(current_user_id.get() or 0, "deepseek-search", "search",
                     0, 0, source="cloud")
    except Exception:
        pass
    out = []
    for r in results:
        title = (r.get("title") or "").strip()
        url = (r.get("url") or "").strip()
        if not title or not url.startswith("http"):
            continue
        snippet = (r.get("summary") or r.get("snippet") or "").strip()  # 面向模型的长摘要优先
        # 剥掉摘要里的 markdown 标题符号（summary 常以 # 标题 开头）
        snippet = re.sub(r"(?m)^#+\s*", "", snippet)
        out.append({
            "title": title[:120],
            "url": url[:300],
            "snippet": snippet[:300],
            "date": r.get("date") or "",
            "authority": r.get("authority"),
        })
    return out


def web_search(query: str, max_results: int = SEARCH_MAX_RESULTS) -> List[Dict]:
    """网页搜索（DeepSeek 官方优先 → Bing → DDG 三级兜底）→ [{title, url, snippet, answer?}]

    query 过短（<2 字）直接返回 []——单字查询必然跑偏（曾出现「大」）。
    """
    q = (query or "").strip()
    if len(q) < 2:
        return []
    for searcher in (_search_deepseek, _search_bing, _search_ddg):
        try:
            results = searcher(q, max_results)
            if results:
                return _dedup_domains(results, max_results)
        except Exception:
            continue
    return []


def format_search_results(results: List[Dict]) -> str:
    """结果 → 模型可读文本（markdown 链接 + 来源域名；前端气泡可点击直达）"""
    if not results:
        return "未找到相关结果（搜索服务暂不可用或结果为空）"
    lines = []
    n = 0
    for r in results:
        if r.get("answer"):
            lines.append(f"**直接答案**：{r['snippet']}")
            continue
        n += 1
        dom = _domain_of(r["url"]) or "来源"
        lines.append(f"{n}. [{r['title']}]({r['url']}) — {dom}")
        if r["snippet"]:
            lines.append(f"   {r['snippet']}")
    return "\n".join(lines)
