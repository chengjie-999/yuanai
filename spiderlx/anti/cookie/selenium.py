import os.path
import random

import time

from spiderlx.core.save.save_data import root_path


def get_cookie(web_driver, cookie_file_path):
    input('需手动登录【登录成功后，点击回车即可】：')

    # 获取所有的cookie并保存
    cookies = web_driver.get_cookies()

    with open(cookie_file_path, 'w', encoding='utf-8') as f:
        f.write(str(cookies))
    print('登录信息已保存！！！')


def use_cookie(web_driver, name, url):
    # 格式化文件名
    root = root_path()
    cookie_file_path = rf'{root}\web_cookie'
    if not os.path.exists(cookie_file_path):
        os.makedirs(cookie_file_path)

    # 1.1 使用cookie
    cookie = os.path.join(cookie_file_path, f'【{name}】cookies.txt')
    if not os.path.exists(cookie):
        get_cookie(web_driver, cookie)
    with open(cookie, mode='r', encoding='utf-8') as f:
        cookies = eval(f.read())
    for cookie in cookies:
        web_driver.add_cookie(cookie)
    print('cookie添加成功！！！')
    time.sleep(random.randint(3, 5))

    # 1.2 重新发起请求
    web_driver.get(url)
    time.sleep(random.randint(3, 5))

