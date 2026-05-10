"""HTTP 请求和 HTML 解析 — 纯函数，无状态。"""
import base64
from typing import Dict, List


def fetch_url(url: str, retype: str = "text") -> str:
    """GET 请求，返回 'text' | 'json' | 'content'(base64)。"""
    import requests

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    if retype == "json":
        return resp.text
    elif retype == "content":
        return base64.b64encode(resp.content).decode()
    return resp.text


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
