"""HTTP 请求和 HTML 解析 — 纯函数，无状态。"""
import base64
from typing import Dict, List

# fetch_url 响应上限（S1.4：parse_html 只用前段文本，防大响应打爆内存）
FETCH_URL_MAX_BYTES = 5 * 1024 * 1024


def fetch_url(url: str, retype: str = "text") -> str:
    """GET 请求，返回 'text' | 'json' | 'content'(base64)。

    S1.4/S1.5 加固：走 safe_fetch 收口（SSRF 守卫 + 逐跳重校验 + DNS 钉住 +
    5MB 流式截断）。lazy import 保持本模块纯函数属性（spiderlx 依赖 requests）。
    """
    from spiderlx.core.requests.safe_fetch import safe_get

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    result = safe_get(url, headers=headers, timeout=15, max_bytes=FETCH_URL_MAX_BYTES)
    result.raise_for_status()
    if retype == "json":
        return result.text
    elif retype == "content":
        return base64.b64encode(result.content).decode()
    return result.text


def parse_html(html: str) -> Dict:
    """解析 HTML，返回 {title, text, links}。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        txt = a.get_text(strip=True)[:60]
        if href.startswith("http") or href.startswith("/"):
            links.append({"url": href, "text": txt or href[:30]})
    return {"title": title, "text": text, "links": links}
