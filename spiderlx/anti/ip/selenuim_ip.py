from selenium import webdriver
import time

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from spiderlx.anti.ip.core import get_random_proxy


def main():
    # 配置谷歌浏览器的启动参数，使用代理  ***********
    proxy = get_random_proxy()
    options = Options()
    options.add_argument(f'--proxy-server={proxy}')  # 添加命令行参数

    # 1. 加载驱动
    driver = webdriver.Chrome(service=Service(executable_path=r"D:\python\chromedriver.exe"))
    driver.maximize_window()  # 窗口最大化

    driver.get('https://www.zhihu.com')  # 网址替换
    time.sleep(5)

    # 2. 解析页面
    print(driver.page_source)

    # -1. 关闭浏览器
    time.sleep(5)
    driver.close()


if __name__ == '__main__':
    main()