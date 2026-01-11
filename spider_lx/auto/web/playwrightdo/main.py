import random
import time
from playwright.sync_api import sync_playwright, Playwright
from spider_lx.save_data.urls import web_urls
# 导入改造后的cookie处理函数（替换原selenium版本）
from spider_lx.anti.cookie.playwright import use_cookie


def able_web():
    """
    可视化加载现有网站信息（逻辑不变）
    :return: 网站信息字典 {code: name}
    """
    info = {}
    code = 0
    for web in web_urls:
        for name in web:
            info[code] = name
        code += 1

    print('现支持的网站信息如下————')
    print(info)
    return info


def open_web(context, page, info, name='', code=None, url=None, login=True):
    """
    适配Playwright：打开指定网站并处理Cookie登录
    :param context: Playwright浏览器上下文（绑定Cookie）
    :param page: Playwright页面对象（页面操作）
    :param info: 网站信息字典
    :param name: 网站名称
    :param code: 网站编码
    :param url: 手动输入的网址
    :return: 网站名称
    """
    # 新增：校验URL是否为空，避免报错
    if not any([code, name, url]):
        raise ValueError("必须传入code/name/url其中一个参数！")

    # 2.1 获取目标网站信息（逻辑不变，仅替换页面跳转方式）
    if code:
        code = int(code)
        name = info[code]
        url = web_urls[code][name][1][0]
    elif name:
        for website in web_urls:
            if name in website.keys():
                url = website[name][1][0]
                break
        else:
            raise ValueError(f"未找到名称为【{name}】的网站！")
    elif url:
        name = '未命名网站'

    print(f'准备访问：{name} | {url}')
    # Playwright页面跳转（增加异常捕获）

    # 3. 处理登录问题（调用改造后的Playwright版use_cookie）
    if not context.cookies([url]) and login:
        cookies = use_cookie(page=page, name=name, url=url)
        context.add_cookies(cookies)
    try:
        page.goto(url)
    except Exception as e:
        raise RuntimeError(f"访问URL失败：{url} | 错误：{e}")

    time.sleep(random.randint(3, 6))  # 保留拟人休眠

    # 4. 网站检验（Playwright获取页面标题）
    t = page.title()
    if name in t:
        print(f'【{name}】网站已成功打开！！！')
    return name


def init_playwright_browser(p: Playwright, headless=False):
    """
    配置Playwright Chrome浏览器（替代原selenium的chrome()函数）
    :param p: Playwright实例
    :param headless: 是否无头模式
    :return: browser, context, page
    """
    # 1. 配置浏览器启动参数（反检测 + 模拟真实浏览器）
    browser = p.chromium.launch(
        headless=headless,
        args=[
            # 禁用自动化检测
            "--disable-blink-features=AutomationControlled",
            # 模拟真实窗口大小
            # "--start-maximized",
            # 禁用扩展
            "--disable-extensions",
            # 禁用GPU加速（避免部分环境报错）
            "--disable-gpu",
        ],
        # 禁用默认的自动化标识
        channel="chrome",  # 使用系统安装的Chrome（更贴近真实环境）
    )

    # 2. 创建上下文（核心：配置反检测 + Cookie隔离）
    context = browser.new_context(
        # 设置真实User-Agent（与原selenium一致）
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # 禁用自动化提示
        viewport=None,  # 配合--start-maximized使用
        # 启用JavaScript（默认开启，显式声明）
        java_script_enabled=True,
        # 模拟真实时区/语言
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
        # 禁用指纹识别（可选，增强反检测）
        permissions=["geolocation"],
    )

    # 3. 移除Playwright的自动化标识（关键反检测步骤）
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        delete window.__playwright_evaluation_script__;
    """)

    # 4. 创建页面并最大化
    page = context.new_page()

    return browser, context, page


def main():
    """
    Playwright主程序入口（替代原selenium主函数）
    """
    with sync_playwright() as p:
        # 1. 初始化Playwright浏览器（替代原chrome()函数）
        browser, context, page = init_playwright_browser(p, headless=False)

        try:
            # 2. 加载网站信息
            info = able_web()

            # 新增：让用户选择要访问的网站（解决URL为空问题）
            print("\n请选择要访问的网站（输入对应数字）：")
            for code, name in info.items():
                print(f"{code} → {name}")

            # 获取用户输入
            while True:
                user_input = input("请输入网站编码（如0）：").strip()
                if user_input.isdigit():
                    break
                print(f"输入无效！请输入{list(info.keys())}中的数字")

            code = user_input

            # 3. 打开目标网站（传入用户选择的code）
            name = open_web(context, page, info, code=code)

            print(f'\n当前访问网站：{name}')

            # 4. 解析数据（保留原业务逻辑，替换为Playwright页面操作）
            try:
                if name == '小猿众包':
                    # 示例：小猿众包页面解析逻辑（替换为Playwright API）
                    # page.locator('xxx').click()  # 点击元素
                    # text = page.locator('xxx').text_content()  # 获取文本
                    print(f'开始解析【{name}】数据...')
            except Exception as e:
                print(f'解析数据异常：{e.args}')

            input('\n运行结束，按回车关闭浏览器...')
        except Exception as e:
            print(f'程序执行异常：{e}')
            input('按回车退出...')
        finally:
            # 关闭资源（Playwright规范关闭顺序）
            page.close()
            context.close()
            browser.close()


if __name__ == '__main__':
    main()
