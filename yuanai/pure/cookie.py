"""Cookie 格式转换 — 纯函数。"""
from typing import Optional, Dict


def cookies_to_dict(site_name: str) -> Optional[Dict]:
    """读取本地 Cookie 文件 → requests 用的 {key: value} 字典。"""
    from spiderlx.anti.cookie.core import local_cookies, selenium_cookie_to_requests_param
    cookies = local_cookies(site_name)
    if not cookies:
        return None
    return selenium_cookie_to_requests_param(cookies)


def cookies_to_header_str(site_name: str, filter_domain: str = "") -> Optional[str]:
    """读取本地 Cookie 文件 → HTTP Header 字符串。"""
    from spiderlx.anti.cookie.core import local_cookies, selenium_cookie_to_header
    cookies = local_cookies(site_name)
    if not cookies:
        return None
    kw = {"filter_domain": filter_domain} if filter_domain else {}
    return selenium_cookie_to_header(cookies, **kw)
