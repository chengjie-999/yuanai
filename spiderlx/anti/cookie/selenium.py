import os
import json
import random
import time
from utils.data_path import root_path


def get_cookie(web_driver, cookie_file_path):
    """
    获取并保存登录后的Cookie到JSON文件
    :param web_driver: WebDriver实例
    :param cookie_file_path: Cookie文件保存路径
    """
    input('需手动登录【登录成功后，点击回车即可】：')

    # 获取所有的cookie
    cookies = web_driver.get_cookies()

    # 确保目录存在
    os.makedirs(os.path.dirname(cookie_file_path), exist_ok=True)

    # 以JSON格式保存Cookie（替代原有的str()方式）
    with open(cookie_file_path, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=4)

    print('登录信息已保存！！！')


def use_cookie(web_driver, name, url):
    """
    从JSON文件加载Cookie并应用到WebDriver
    :param web_driver: WebDriver实例
    :param name: 站点名称（用于生成Cookie文件名）
    :param url: 目标访问URL
    """
    # 构建Cookie文件完整路径
    root = root_path()
    cookie_dir = os.path.join(root, 'data', 'web_cookie')
    cookie_file_path = os.path.join(cookie_dir, f'【{name}】cookies.json')  # 改为json后缀

    # 如果Cookie文件不存在，先获取并保存
    if not os.path.exists(cookie_file_path):
        get_cookie(web_driver, cookie_file_path)
        return None

    # 从JSON文件读取Cookie（替代不安全的eval()）
    try:
        with open(cookie_file_path, 'r', encoding='utf-8') as f:
            cookies = json.load(f)

        # 逐个添加Cookie到浏览器
        for cookie in cookies:
            # 兼容不同浏览器的Cookie格式（如expiry字段类型问题）
            if 'expiry' in cookie and isinstance(cookie['expiry'], float):
                cookie['expiry'] = int(cookie['expiry'])
            web_driver.add_cookie(cookie)

        print('Cookie添加成功！！！')
    except json.JSONDecodeError:
        print(f'错误：{cookie_file_path} 文件格式损坏，将重新获取Cookie')
        os.remove(cookie_file_path)  # 删除损坏的文件
        get_cookie(web_driver, cookie_file_path)  # 重新获取
    except Exception as e:
        print(f'加载Cookie时出错：{str(e)}')
        raise

    # 随机等待后重新访问目标URL
    time.sleep(random.randint(3, 5))
    web_driver.get(url)
    time.sleep(random.randint(3, 5))
    return True
