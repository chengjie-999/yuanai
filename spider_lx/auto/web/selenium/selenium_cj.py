import random
import time

from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from spider_lx.parse_data import xiao_yuan
from spider_lx.save_data.urls import web_urls
from spider_lx.anti import selenium_cookie


def able_web():
    """
    可视化加载现有网站
    :return:
    """
    # 展示现有网站信息
    info = {}
    code = 0
    for web in web_urls:
        for name in web:
            info[code] = name
        code += 1

    print('现支持的网站信息如下————')
    print(info)
    return info


def app_choose_web(web_driver, info, code=1):
    # 2.1 获取目标网站信息，开始访问
    code = int(code)
    name = info[code]
    url = web_urls[code][name][1][0]

    #
    web_driver.get(url)
    time.sleep(random.randint(3, 6))  # 拟人

    # 3. 处理登录问题
    # choose = st.text_input('是否处理登陆问题：(y/n)')
    selenium_cookie.use_cookie(web_driver, name, url)

    # 4. 网站检验
    t = web_driver.title
    if name in t:
        print(f'【{name}】网站已成功打开！！！')
    return name


def chrome():
    """
    配置Chrome选项，创建Chrome
    :return:
    """
    # 创建选项对象
    chrome_options = Options()

    # 1. 添加真实 User-Agent（模拟浏览器，从自己浏览器复制）
    chrome_options.add_argument(
        'user-agent='
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')  # 关键：禁用自动化检测

    # 2. 禁用自动化标识（关键，避免被网站检测）
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    # 1. 浏览器驱动
    # driver = Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver = Chrome(service=Service(executable_path=r"D:\chromedriver-win64\chromedriver.exe"), options=chrome_options)
    driver.maximize_window()
    return driver


def main():
    """
    selenium主程序入口
    :return:
    """
    # 唤醒并配置浏览器
    driver = chrome()
    # while 1:
    # 2. 加载执行的网页
    info = able_web()
    name = app_choose_web(driver, info, 0)
    print(name)
    # 3. 解析数据
    try:
        if name == '小猿众包':
            xiao_yuan.app_go(driver)
    except Exception as e:
        print(e.args)
    input('运行结束')
    # -1. 关闭浏览器
    driver.quit()


if __name__ == '__main__':
    pass
