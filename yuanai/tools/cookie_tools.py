from langchain_core.tools import tool


@tool
def cookies_to_requests(site_name: str) -> str:
    """
    将浏览器中指定网站的 Cookie 转换为 requests 库可用的 cookies 参数字典。
    参数 site_name: 网站名称（如 '知乎'、'小猿众包'），对应 data/web_cookie/ 下的 Cookie 文件
    """
    try:
        import json
        from spiderlx.anti.cookie.core import local_cookies, selenium_cookie_to_requests_param
        cookies = local_cookies(site_name)
        if not cookies:
            return f"❌ 未找到 [{site_name}] 的 Cookie 文件，请先登录后保存 Cookie"
        result = selenium_cookie_to_requests_param(cookies)
        return f"✅ [{site_name}] Cookie 已转换，共 {len(result)} 个键值对。\n数据：{json.dumps(result, ensure_ascii=False)}"
    except Exception as e:
        return f"❌ 转换失败: {e}"


@tool
def cookies_to_header(site_name: str, filter_domain: str = "") -> str:
    """
    将浏览器中指定网站的 Cookie 转换为 requests 库可用的 Header。
    参数 site_name: 网站名称
    参数 filter_domain: 可选，只保留指定域名的 Cookie（如 '.zhihu.com'）
    """
    try:
        from spiderlx.anti.cookie.core import local_cookies, selenium_cookie_to_header
        cookies = local_cookies(site_name)
        if not cookies:
            return f"❌ 未找到 [{site_name}] 的 Cookie 文件"
        kw = {}
        if filter_domain:
            kw["filter_domain"] = filter_domain
        result = selenium_cookie_to_header(cookies, **kw)
        return f"✅ [{site_name}] Cookie Header 已生成。\n{result}"
    except Exception as e:
        return f"❌ 转换失败: {e}"
