import os
import json
import random
import time

from selenium.webdriver.chrome.webdriver import WebDriver

from spiderlx.anti.cookie.core import local_cookies
from utils.data_path import root_path


def get_cookie(web_driver: WebDriver, name):
    """
    完成登陆后，获取并保存登录后的Cookie到JSON文件
    :param web_driver: WebDriver实例
    """
    cookie_file_path = os.path.join(root_path(), 'data', 'web_cookie', f'【{name}】cookies.json')
    # 获取所有的cookie
    cookies = web_driver.get_cookies()

    # 确保目录存在
    os.makedirs(os.path.dirname(cookie_file_path), exist_ok=True)

    # 以JSON格式保存Cookie（替代原有的str()方式）
    with open(cookie_file_path, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=4)

    print('登录信息已保存！！！')
    return True


def use_cookie(web_driver: WebDriver, name, url):
    """
    从JSON文件加载Cookie并应用到WebDriver
    :param web_driver: WebDriver实例
    :param name: 站点名称（用于生成Cookie文件名）
    :param url: 目标访问URL
    """
    cookies = local_cookies(name)
    if not cookies:
        return False
    else:
        # 逐个添加Cookie到浏览器
        for cookie in cookies:
            # 兼容不同浏览器的Cookie格式（如expiry字段类型问题）
            if 'expiry' in cookie and isinstance(cookie['expiry'], float):
                cookie['expiry'] = int(cookie['expiry'])
            web_driver.add_cookie(cookie)

        print('Cookie添加成功！！！')

        # 随机等待后重新访问目标URL
        time.sleep(random.randint(3, 5))
        web_driver.get(url)
        time.sleep(random.randint(3, 5))
        return True
