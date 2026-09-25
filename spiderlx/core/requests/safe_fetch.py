"""SSRF 安全请求 — 全仓 requests 直连调用点唯一收口（S1.5 加固）。

- safe_get / safe_get_stream：allow_redirects=False + 手工逐跳重校验（≤5 跳，
  每一跳的 Location 都过 validate_url，含 DNS 解析后 IP 检查）
- DNS 钉住：解析一次、全部 IP 过黑名单后，TCP 连接固定到该 IP；
  Host 头与 TLS SNI/证书校验保留原域名（不关 verify）
- 流式读取 + 响应体积上限（默认 20MB，env SAFE_FETCH_MAX_BYTES 可调）
"""
import os
from typing import Callable, Optional
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException

from yuanai_core.pure.ssrf import resolve_checked, validate_url

MAX_RESPONSE_BYTES = int(os.getenv("SAFE_FETCH_MAX_BYTES", str(20 * 1024 * 1024)))
MAX_REDIRECTS = 5


class SafeFetchResult:
    """安全请求结果（内容已全量读入或截断）。"""

    __slots__ = ("status_code", "url", "headers", "content", "truncated")

    def __init__(self, status_code: int, url: str, headers, content: bytes, truncated: bool):
        self.status_code = status_code
        self.url = url
        self.headers = headers
        self.content = content
        self.truncated = truncated

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", "replace")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RequestException(f"HTTP {self.status_code}（{self.url}）")


class _PinnedIPAdapter(HTTPAdapter):
    """DNS 钉住：TCP 连接固定到已校验 IP；Host 头 + TLS SNI/证书校验保留原域名。

    注意：若环境配置了 HTTP(S) 代理，连接将走代理（requests 的 proxy 机制优先），
    钉住不生效——代理是独立信任边界。
    """

    def __init__(self, hostname: str, ip: str, scheme: str):
        super().__init__()
        self._hostname = hostname
        self._ip = ip
        self._scheme = scheme

    def send(self, request, **kwargs):
        parsed = urlparse(request.url)
        port = f":{parsed.port}" if parsed.port else ""
        host_for_url = f"[{self._ip}]" if ":" in self._ip else self._ip
        request.url = f"{parsed.scheme}://{host_for_url}{port}{parsed.path or '/'}"
        if parsed.query:
            request.url += f"?{parsed.query}"
        # Host 头保留原域名（部分站点按 Host 路由）
        request.headers["Host"] = f"{self._hostname}{port}"
        # TLS 专属：SNI + 证书校验用原域名（HTTP 池不接受这些参数）
        if self._scheme == "https":
            pool_kwargs = self.poolmanager.connection_pool_kw
            pool_kwargs["server_hostname"] = self._hostname
            pool_kwargs["assert_hostname"] = self._hostname
        return super().send(request, **kwargs)


def _read_limited(resp, limit: int, stream_cb: Optional[Callable[[bytes], None]]) -> SafeFetchResult:
    """流式读取并限体积；stream_cb 提供时边读边回调（下载场景），否则累积返回。"""
    content = bytearray()
    truncated = False
    try:
        for chunk in resp.iter_content(64 * 1024):
            if not chunk:
                continue
            if len(content) + len(chunk) > limit:
                truncated = True
                remaining = max(0, limit - len(content))
                if remaining and stream_cb:
                    stream_cb(chunk[:remaining])
                break
            if stream_cb:
                stream_cb(chunk)
            content.extend(chunk)
    finally:
        resp.close()
    return SafeFetchResult(resp.status_code, resp.url, resp.headers, bytes(content), truncated)


def safe_get(url: str, method: str = "GET", headers: Optional[dict] = None,
             timeout: float = 15, max_bytes: Optional[int] = None,
             stream_cb: Optional[Callable[[bytes], None]] = None,
             **kwargs) -> SafeFetchResult:
    """单一安全请求入口：逐跳重校验（≤5 跳）+ DNS 钉住 + 体积上限。

    - stream_cb：提供时走下载模式（每块回调，收满即停）
    - max_bytes：None 用全局 MAX_RESPONSE_BYTES（20MB）
    - 违规抛 ValueError（URL 非法/内网）或 RequestException（网络/重定向）
    """
    limit = max_bytes if max_bytes is not None else MAX_RESPONSE_BYTES
    current = validate_url(url)
    for hop in range(MAX_REDIRECTS + 1):
        host = urlparse(current).hostname
        scheme = urlparse(current).scheme
        # 解析一次并全检，然后钉住第一个 IP（DNS rebinding 无法在连接时换目标）
        ips = resolve_checked(host)
        session = requests.Session()
        session.mount(f"{scheme}://", _PinnedIPAdapter(host, ips[0], scheme))
        resp = session.request(method, current, headers=headers, timeout=timeout,
                               allow_redirects=False, stream=True, **kwargs)
        if resp.is_redirect or resp.is_permanent_redirect:
            loc = resp.headers.get("Location", "")
            if not loc:
                raise RequestException(f"重定向响应缺少 Location: {current}")
            # 每一跳重新校验（含解析后 IP 检查；非 http(s) 直接拒）
            next_url = validate_url(urljoin(current, loc))
            resp.close()
            current = next_url
            continue
        result = _read_limited(resp, limit, stream_cb)
        return SafeFetchResult(result.status_code, current, result.headers,
                               result.content, result.truncated)
    raise RequestException(f"重定向次数超过 {MAX_REDIRECTS} 跳: {url}")
