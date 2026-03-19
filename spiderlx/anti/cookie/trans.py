def selenium_cookies_to_header(cookies: list) -> str:
    """
    将 Selenium 获取的 Cookie 列表（对象格式）转换为请求头可用的 Cookie 字符串
    :param cookies: driver.get_cookies() 返回的 Cookie 列表
    :return: 拼接好的 Cookie 字符串，如 "name1=value1; name2=value2"
    """
    if not isinstance(cookies, list):
        raise ValueError("输入必须是 Selenium 返回的 Cookie 列表")

    cookie_str = ""
    for cookie in cookies:
        # 只取 name 和 value 拼接，忽略其他属性
        if "name" in cookie and "value" in cookie:
            cookie_str += f"{cookie['name']}={cookie['value']};"

    # 移除最后一个多余的分号，避免格式错误
    return cookie_str.rstrip(";")


def header_cookie_to_selenium(cookie_str: str, domain: str, path="/") -> list:
    """
    将请求头的 Cookie 字符串转换为 Selenium 可添加的 Cookie 对象列表
    :param cookie_str: 请求头中的 Cookie 字符串，如 "name1=value1; name2=value2"
    :param domain: Cookie 所属域名（必填，如 ".baidu.com"）
    :param path: Cookie 生效路径（默认 "/"）
    :return: 可直接传入 driver.add_cookie() 的 Cookie 字典列表
    """
    if not isinstance(cookie_str, str) or not domain:
        raise ValueError("Cookie 字符串和域名不能为空")

    selenium_cookies = []
    # 按分号分割 Cookie 键值对，处理可能的空格
    cookie_pairs = [pair.strip() for pair in cookie_str.split(";") if pair.strip()]

    for pair in cookie_pairs:
        if "=" in pair:
            name, value = pair.split("=", 1)  # 处理 value 中包含等号的情况
            selenium_cookie = {
                "name": name.strip(),
                "value": value.strip(),
                "domain": domain,  # Selenium 必须指定域名，否则 Cookie 无效
                "path": path,  # Selenium 必须指定路径，默认 "/"
                "secure": False,  # 非 HTTPS 网站设为 False，HTTPS 设为 True
                "httpOnly": False,  # 一般设为 False，避免无法通过 Selenium 操作
                "expiry": None  # 过期时间，None 表示会话级 Cookie
            }
            selenium_cookies.append(selenium_cookie)

    return selenium_cookies


# ------------------- 测试示例 -------------------
if __name__ == "__main__":
    # 1. 模拟 Selenium 获取的 Cookie 列表（实际使用时替换为 driver.get_cookies()）
    mock_selenium_cookies = [
        {"name": "sessionid", "value": "123456abc", "domain": ".baidu.com", "path": "/"},
        {"name": "BAIDUID", "value": "7890def", "domain": ".baidu.com", "path": "/"},
        {"name": "H_PS_PSSID", "value": "1001_2002", "domain": ".baidu.com", "path": "/"}
    ]

    # 转换1：Selenium → 请求头
    header_cookie = selenium_cookies_to_header(mock_selenium_cookies)
    print("✅ Selenium → 请求头 Cookie 字符串：")
    print(header_cookie)
    # 输出：sessionid=123456abc; BAIDUID=7890def; H_PS_PSSID=1001_2002

    # 转换2：请求头 → Selenium（现在无需传 path，用默认值即可）
    selenium_cookies = header_cookie_to_selenium(header_cookie, domain=".baidu.com")
    print("\n✅ 请求头 → Selenium Cookie 列表：")
    for cookie in selenium_cookies:
        print(cookie)
