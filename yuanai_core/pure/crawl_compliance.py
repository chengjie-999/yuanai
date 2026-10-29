"""C10 爬虫合规基建（2026-10-29）——robots 检查 + 统一可识别 UA + 按域限流。

合规审计第 12 条：全仓无 robots.txt 解析、多处伪装/随机 UA、采集无按域限流。
本模块为唯一收口：通用网页采集脚本与 fetch_url 工具经 guarded_get 三段式
（robots 判定 → 同域限流 → safe_get SSRF 安全请求）执行，拒绝采集 robots
禁止的路径。纯函数 + 模块级缓存，无框架依赖。
"""

import logging
import threading
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# 统一可识别 UA（《互联网信息服务算法推荐管理规定》爬虫透明度要求；
# 联系信息指向官网公开页——不再是伪装的浏览器 UA）
BOT_UA = "XiaoYuanBot/1.0 (+https://cjyuanai.cn/about)"

# robots 判定缓存：{netloc: (verdict, fetched_ts)}，TTL 1 小时
_ROBOTS_CACHE: dict = {}
_ROBOTS_TTL = 3600.0
# 同域请求最小间隔（秒）：限流第一道（robots Crawl-delay 其次）
MIN_INTERVAL = 1.0
_LAST_FETCH: dict = {}
_LOCK = threading.Lock()


def _netloc_of(url: str) -> str:
    return (urlparse(url).netloc or "").lower()


def _robots_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}/robots.txt"


def _parse_robots(text: str) -> tuple:
    """解析 robots.txt → (disallow_rules: list[str], crawl_delay: float|None)
    只取 XiaoyuanBot 专属组，否则 * 组；规则为路径前缀匹配（含空 = 全放行）。"""
    lines = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        lines.append((key.strip().lower(), val.strip()))

    # 找本 UA 组；无则 *
    groups: dict = {}
    current = None
    for key, val in lines:
        if key == "user-agent":
            current = val.lower()
            groups.setdefault(current, {"disallow": [], "delay": None})
        elif current is not None and groups.get(current) is not None:
            g = groups[current]
            if key == "disallow":
                g["disallow"].append(val)
            elif key == "crawl-delay":
                try:
                    g["delay"] = float(val)
                except ValueError:
                    pass

    mine = groups.get("xiaoyuanbot")
    if mine is None:
        mine = groups.get("*")
    if mine is None:
        return [], None
    return mine["disallow"], mine["delay"]


def check_robots(url: str) -> tuple:
    """检查 robots.txt → (verdict, note)。
    verdict ∈ allow/deny/unknown（unknown = 取不到 robots 或解析失败，放行但标注）。"""
    netloc = _netloc_of(url)
    if not netloc:
        return "unknown", "URL 无有效域名"
    now = time.time()
    hit = _ROBOTS_CACHE.get(netloc)
    if hit and now - hit[1] < _ROBOTS_TTL:
        return hit[0], ""
    verdict, note = "unknown", ""
    try:
        from spiderlx.core.requests.safe_fetch import safe_get
        resp = safe_get(_robots_url(url), timeout=8, max_bytes=512 * 1024,
                        headers={"User-Agent": BOT_UA})
        if resp.status_code in (200, 301):
            rules, _delay = _parse_robots(resp.text)
            path = urlparse(url).path or "/"
            denied = any(rule and path.startswith(rule) for rule in rules)
            verdict = "deny" if denied else "allow"
            note = ""
        else:
            note = f"robots 不可用（HTTP {resp.status_code}）"
    except Exception as e:
        note = f"robots 获取失败: {e}"
    _ROBOTS_CACHE[netloc] = ((verdict, note), now)
    return verdict, note


def throttle(domain: str, min_interval: float = MIN_INTERVAL) -> None:
    """同域限流：距上次请求不足 min_interval 则等待（模块级表，线程安全）"""
    if not domain:
        return
    with _LOCK:
        last = _LAST_FETCH.get(domain)
        if last:
            wait = min_interval - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
        _LAST_FETCH[domain] = time.time()


def guarded_get(url: str, timeout: float = 15, max_bytes: int | None = None,
                method: str = "GET"):
    """三段式合规请求：robots 判定 → 同域限流 → safe_get（SSRF 守卫 + 逐跳重校验）。

    robots deny → raise PermissionError（调用方应拒绝采集并告知原因）。
    返回 safe_get 的 SafeFetchResult。
    """
    from spiderlx.core.requests.safe_fetch import safe_get
    verdict, note = check_robots(url)
    if verdict == "deny":
        raise PermissionError(f"robots.txt 禁止自动采集该路径（{url}）")
    throttle(_netloc_of(url))
    return safe_get(url, method=method, timeout=timeout,
                    max_bytes=max_bytes,
                    headers={"User-Agent": BOT_UA})
