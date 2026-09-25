"""SSRF URL 守卫 — 纯函数（仅 stdlib），云边共用黑名单单一来源。

覆盖绕过面（S1.5 加固）：
- IPv4-mapped IPv6（::ffff:127.0.0.1）归一化转 IPv4 后比对
- 十进制/八进制 IP（2130706433 等）经 getaddrinfo 解析后比对
- URL userinfo（@）拒绝
- 云 metadata 主机黑名单（AWS/GCP/Azure/腾讯云 + 常见 IP）
- 域名的全部 DNS 解析结果逐一过检（防 rebinding 第一层）
"""
import ipaddress
import re
import socket
import struct
from typing import List, Optional
from urllib.parse import urlparse

# 禁止访问的内网/保留地址段
BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),   # CGNAT
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::ffff:0:0/96"),   # IPv4-mapped IPv6
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::/128"),
]

# 云 metadata 主机黑名单（S1.5 补充 azure/腾讯云）
BLOCKED_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "169.254.169.254",
    "metadata.azure.com",
    "169.254.170.2",
    "100.100.100.200",
    "metadata.tencentyun.com",
}


def check_ip(addr_str: str) -> ipaddress._BaseAddress:
    """归一化（IPv4-mapped → IPv4、去 zone id）后做内网段比对，命中抛 ValueError。"""
    raw = str(addr_str).split("%")[0]
    addr = ipaddress.ip_address(raw)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    for net in BLOCKED_NETWORKS:
        if addr in net:
            raise ValueError("禁止访问内网地址")
    return addr


def _literal_ip_or_none(hostname: str) -> Optional[str]:
    """IP 字面量（点分/压缩 IPv6/十进制/0x 十六进制）→ IP 字符串；非字面量返回 None。

    Windows 的 getaddrinfo 不做 inet_aton 式转换，2130706433 这类十进制 IP
    必须显式换算后再比对（审计绕过面之一）。
    """
    try:
        return str(ipaddress.ip_address(hostname))
    except ValueError:
        pass
    if re.fullmatch(r"\d+", hostname):  # 十进制：2130706433 → 127.0.0.1
        n = int(hostname, 10)
        if n < 2 ** 32:
            return socket.inet_ntoa(struct.pack("!I", n))
    if re.fullmatch(r"0x[0-9a-fA-F]+", hostname):  # 十六进制：0x7f000001
        n = int(hostname, 16)
        if n < 2 ** 32:
            return socket.inet_ntoa(struct.pack("!I", n))
    return None


def resolve_checked(hostname: str) -> List[str]:
    """DNS 解析：全部结果逐一过内网黑名单（防 rebinding 第一层）。失败抛 ValueError。"""
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError(f"无法解析主机名: {hostname}") from None
    ips: List[str] = []
    for item in infos:
        ip = item[4][0]
        check_ip(ip)
        if ip not in ips:
            ips.append(ip)
    if not ips:
        raise ValueError(f"无法解析主机名: {hostname}")
    return ips


def validate_url(url: str) -> str:
    """验证并清理 URL，防止 SSRF。返回规范化后的 URL，无效则抛出 ValueError。"""
    if not url or not isinstance(url, str):
        raise ValueError("URL 不能为空")

    url = url.strip()
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("仅支持 http/https 协议")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("无法解析 URL 主机名")

    if parsed.username or parsed.password:
        raise ValueError("URL 不允许携带用户信息（@）")

    hostname_lower = hostname.lower()
    if hostname_lower in BLOCKED_HOSTS:
        raise ValueError("禁止访问该主机")

    # IP 字面量（含 IPv4-mapped/十进制/十六进制形式）直接比对；域名走 DNS 全检
    literal = _literal_ip_or_none(hostname_lower)
    if literal:
        check_ip(literal)
    else:
        resolve_checked(hostname_lower)

    # 规范化：去 fragment（HTTP 请求不带）
    return parsed._replace(fragment="").geturl()
