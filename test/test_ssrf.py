# -*- coding: utf-8 -*-
"""S1.4/S1.5 SSRF 修复测试 — 全绕过矩阵 + 安全请求行为（纯离线，本地 http.server）

运行：pytest test/test_ssrf.py -v
"""
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')


# ---------------- validate_url 拒绝矩阵（离线，IP 字面量不触发 DNS） ----------------

@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8000/",
    "http://127.0.0.1/",
    "http://10.1.2.3/",
    "http://172.16.0.1/",
    "http://192.168.1.1/",
    "http://169.254.169.254/latest/meta-data/",
    "http://0.0.0.0/",
    "http://100.64.0.1/",          # CGNAT
    "http://[::1]/",
    "http://[::ffff:127.0.0.1]/",  # IPv4-mapped IPv6
    "http://[fe80::1]/",
    "http://[fc00::1]/",
])
def test_validate_url_rejects_internal(url):
    from yuanai_core.pure.ssrf import validate_url
    with pytest.raises(ValueError, match="禁止访问"):
        validate_url(url)


@pytest.mark.parametrize("url", [
    "http://localhost/",
    "http://metadata.google.internal/",
    "http://metadata/",
    "http://metadata.azure.com/",
    "http://169.254.170.2/",
    "http://100.100.100.200/",
    "http://metadata.tencentyun.com/",
])
def test_validate_url_rejects_blocked_hosts(url):
    from yuanai_core.pure.ssrf import validate_url
    with pytest.raises(ValueError):
        validate_url(url)


def test_validate_url_rejects_decimal_ip():
    """十进制 IP 2130706433 → getaddrinfo 解析为 127.0.0.1 → 拒"""
    from yuanai_core.pure.ssrf import validate_url
    with pytest.raises(ValueError, match="禁止访问"):
        validate_url("http://2130706433/")


def test_validate_url_rejects_userinfo():
    """URL 携带 @ userinfo → 拒（127.0.0.1@evil.com 与 evil.com@127.0.0.1 都覆盖）"""
    from yuanai_core.pure.ssrf import validate_url
    with pytest.raises(ValueError, match="用户信息"):
        validate_url("http://127.0.0.1@evil.com/")
    with pytest.raises(ValueError):
        validate_url("http://evil.com@127.0.0.1/")


@pytest.mark.parametrize("url", [
    "ftp://example.com/x",
    "file:///etc/passwd",
    "gopher://127.0.0.1/",
    "javascript:alert(1)",
    "",
    None,
    "not-a-url",
])
def test_validate_url_rejects_misc(url):
    from yuanai_core.pure.ssrf import validate_url
    with pytest.raises(ValueError):
        validate_url(url)


def test_validate_url_accepts_public(monkeypatch):
    """公网域名放行（DNS 打桩离线化）"""
    from yuanai_core.pure.ssrf import validate_url

    real_getaddrinfo = socket.getaddrinfo

    def fake(host, *args, **kwargs):
        if host in ("example.com", "www.example.com"):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", fake)
    assert validate_url("https://example.com/path?q=1") == "https://example.com/path?q=1"
    assert validate_url("https://example.com/path#frag").endswith("/path")  # fragment 去除


# ---------------- safe_get 行为（本地 http.server，放开 127.0.0.1） ----------------

class _Handler(BaseHTTPRequestHandler):
    """测试服务器：重定向链 / Host 断言 / 大响应"""

    def log_message(self, *args):  # 静音
        pass

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = self.path
        if path.startswith("/redirect-to-localhost"):
            self.send_response(302)
            self.send_header("Location", f"http://localhost:{self.server.server_port}/target")
            self.end_headers()
        elif path.startswith("/redirect-to-ftp"):
            self.send_response(302)
            self.send_header("Location", "ftp://example.com/file")
            self.end_headers()
        elif path.startswith("/r"):
            n = int(path[2:])
            if n > 0:
                self.send_response(302)
                self.send_header("Location", f"/r{n - 1}")
                self.end_headers()
            else:
                self._ok("end")
        elif path.startswith("/big"):
            body = b"x" * (300 * 1024)
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except OSError:
                pass  # 客户端到达上限主动断开（截断场景，正常）
        elif path.startswith("/host"):
            self._ok(self.headers.get("Host", ""))
        else:
            self._ok("hello")

    def _ok(self, body: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body.encode())))
        self.end_headers()
        self.wfile.write(body.encode())


@pytest.fixture(scope="module")
def local_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture()
def allow_local(monkeypatch):
    """放开 127.0.0.1（保留主机黑名单，供「重定向到 localhost 仍拒」测试）"""
    import yuanai_core.pure.ssrf as ssrf
    monkeypatch.setattr(ssrf, "BLOCKED_NETWORKS", [])
    return ssrf


def test_safe_get_ok_and_truncation(local_server, allow_local):
    from spiderlx.core.requests.safe_fetch import safe_get

    r = safe_get(f"{local_server}/target")
    assert r.status_code == 200
    assert r.text == "hello"
    assert r.truncated is False

    r = safe_get(f"{local_server}/big", max_bytes=100 * 1024)
    assert r.truncated is True
    # 收满即止：不超过上限（按 64KB 块粒度，可略小于上限）
    assert len(r.content) <= 100 * 1024


def test_redirect_chain_bounded(local_server, allow_local):
    from spiderlx.core.requests.safe_fetch import safe_get
    from requests.exceptions import RequestException

    r = safe_get(f"{local_server}/r5")  # 5 跳内：通过
    assert r.status_code == 200

    with pytest.raises(RequestException, match="重定向次数"):
        safe_get(f"{local_server}/r6")  # 6 跳：拒绝


def test_redirect_to_blocked_host_rejected(local_server, allow_local):
    """首跳可连，但 Location 指向 localhost → 逐跳重校验拒"""
    from spiderlx.core.requests.safe_fetch import safe_get

    with pytest.raises(ValueError, match="禁止访问"):
        safe_get(f"{local_server}/redirect-to-localhost")


def test_redirect_to_non_http_rejected(local_server, allow_local):
    from spiderlx.core.requests.safe_fetch import safe_get

    with pytest.raises(ValueError, match="http/https"):
        safe_get(f"{local_server}/redirect-to-ftp")


def test_dns_pinning_and_host_header(local_server, allow_local, monkeypatch):
    """DNS 钉住：fake.test 解析到 127.0.0.1 后连接本地；Host 头保留原域名"""
    from spiderlx.core.requests.safe_fetch import safe_get

    real_getaddrinfo = socket.getaddrinfo

    def fake(host, *args, **kwargs):
        if host == "fake.test":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", fake)

    r = safe_get(f"http://fake.test:{local_server.rsplit(':', 1)[1]}/host")
    assert r.status_code == 200
    # 服务器看到的 Host 头必须是原域名（钉住不影响 Host/SNI）
    assert r.text.startswith("fake.test")


def test_stream_cb_download(local_server, allow_local, tmp_path):
    """下载模式：stream_cb 边读边落盘，内容完整"""
    from spiderlx.core.requests.safe_fetch import safe_get

    out = tmp_path / "dl.bin"
    with open(out, "wb") as f:
        r = safe_get(f"{local_server}/big", max_bytes=300 * 1024, stream_cb=f.write)
    assert r.truncated is False
    assert out.stat().st_size == 300 * 1024


# ---------------- 调用点收口回归 ----------------

def test_crawl_fetch_url_rejects_internal():
    """fetch_url 对 SSRF 目标在发请求前即拒（不发 HTTP 请求）"""
    from yuanai_core.pure.crawl import fetch_url

    with pytest.raises(ValueError, match="禁止访问"):
        fetch_url("http://169.254.169.254/latest/meta-data/")


def test_check_url_rejects_internal():
    from yuanai_core.tools import crawl_tools

    # @tool 装饰后模块名是 StructuredTool，取底层 func 调用
    fn = getattr(crawl_tools.check_url, "func", crawl_tools.check_url)
    out = fn("http://127.0.0.1:8000/health")
    assert "不可访问" in out
    assert "禁止访问" in out


def test_fetch_url_works_via_local(local_server, allow_local, monkeypatch):
    """fetch_url 全链路（守卫+截断+返回）在本地服务器上跑通"""
    import yuanai_core.pure.ssrf as ssrf
    from yuanai_core.pure.crawl import fetch_url

    monkeypatch.setattr(ssrf, "BLOCKED_HOSTS", set())  # 本测试不涉及主机黑名单
    r = fetch_url(f"{local_server}/target")
    assert r == "hello"


if __name__ == "__main__":
    print("测试入口：pytest test/test_ssrf.py -v")
