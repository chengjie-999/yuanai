import ipaddress
import random
import socket
import time
import requests
from typing import Literal, Union
from urllib.parse import urlparse
from requests.exceptions import RequestException, JSONDecodeError

from spiderlx.anti.ua import get_random_ua

ReturnType = Literal['text', 'json', 'content']

# 禁止访问的内网地址段
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::/128"),
]

# 禁止访问的 hostname
_BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "169.254.169.254"}


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

    hostname_lower = hostname.lower()
    if hostname_lower in _BLOCKED_HOSTS:
        raise ValueError("禁止访问该主机")

    # 检查是否为 IP 地址
    try:
        addr = ipaddress.ip_address(hostname)
        for net in _BLOCKED_NETWORKS:
            if addr in net:
                raise ValueError("禁止访问内网地址")
    except ValueError as e:
        if "禁止访问" in str(e):
            raise
        # 非 IP 地址，需要 DNS 解析检查
        try:
            resolved_ip = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for item in resolved_ip:
                addr_str = item[4][0]
                addr = ipaddress.ip_address(addr_str)
                for net in _BLOCKED_NETWORKS:
                    if addr in net:
                        raise ValueError("禁止访问内网地址")
        except socket.gaierror:
            raise ValueError(f"无法解析主机名: {hostname}")

    return parsed.geturl()


def get_response_data(
        url: str,
        retype: ReturnType = 'text',
        method: str = 'GET',
        max_retries: int = 2,
        **kwargs
) -> Union[str, dict, list, bytes]:
    """
    发送HTTP请求并按指定类型返回响应数据，内置反爬措施。
    Args:
        url: 请求的URL地址
        retype: 返回数据类型
        method: 请求方法（GET / POST）
        max_retries: 失败重试次数
    """
    url = validate_url(url)
    delay = random.uniform(1.0, 3.0)
    time.sleep(delay)

    for attempt in range(max_retries + 1):
        try:
            headers = {
                'User-Agent': get_random_ua(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': 'https://www.google.com/',
            }
            if method == 'POST':
                resp = requests.post(url, headers=headers, timeout=15, **kwargs)
            else:
                resp = requests.get(url, headers=headers, timeout=15, **kwargs)
            resp.raise_for_status()
            break
        except RequestException as e:
            last_error = e
            if attempt < max_retries:
                wait = random.uniform(2.0, 5.0)
                time.sleep(wait)
            else:
                raise RequestException(f"请求URL失败（已重试{max_retries}次）：{url}，错误：{str(e)}") from e

    if retype == 'text':
        return resp.text
    elif retype == 'json':
        try:
            return resp.json()
        except JSONDecodeError as e:
            raise JSONDecodeError(f"响应内容无法解析为JSON，URL：{url}", doc=resp.text, pos=0) from e
    elif retype == 'content':
        return resp.content
    else:
        raise ValueError(f"无效的retype值：{retype}，仅支持 'text'/'json'/'content'")
