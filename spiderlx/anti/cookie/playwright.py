import os.path
import json  # 替换eval，用json更安全

from utils.data_path import root_path


def get_cookie(page, cookie_file_path):
    """
    适配Playwright：手动登录后获取Cookie并保存到文件
    :param page: Playwright的Page对象（关联Context）
    :param cookie_file_path: Cookie保存路径
    """
    input('需手动登录【登录成功后，点击回车即可】：')

    # Playwright通过Context获取Cookie（而非Page），且返回格式与Selenium兼容
    context = page.context
    cookies = context.cookies()

    # 用json保存（替换str+eval，避免安全风险）
    with open(cookie_file_path, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print('登录信息已保存！！！')


def use_cookie(page, name, url):
    """
    适配Playwright：读取本地Cookie并添加到Context
    :param page: Playwright的Page对象（用于页面操作）
    :param name: 站点名称（用于Cookie文件名）
    :param url: 目标访问URL
    """
    # 格式化文件名（保留原路径逻辑）
    root = root_path()
    cookie_file_path = rf'{root}\web_cookie'
    if not os.path.exists(cookie_file_path):
        os.makedirs(cookie_file_path)

    # 拼接Cookie文件路径
    cookie_file = os.path.join(cookie_file_path, f'【{name}】cookies.json')

    # 若Cookie文件不存在，先手动登录获取
    if not os.path.exists(cookie_file):
        # 先跳转到登录页（确保Page在目标域名下）
        page.goto(url)
        get_cookie(page, cookie_file)

    # 读取Cookie文件（用json.load替换eval，更安全）
    with open(cookie_file, mode='r', encoding='utf-8') as f:
        cookies = json.load(f)

    return cookies
