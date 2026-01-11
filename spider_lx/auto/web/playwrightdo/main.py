import asyncio

from playwright.sync_api import sync_playwright

from spider_lx.auto.web.playwrightdo.anti import anti_crawl


def main():
    with sync_playwright() as p:
        # 1. 启动浏览器，创建上下文（Cookie绑定到Context）
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # 2. 使用Cookie访问目标站点
        use_cookie(
            context=context,
            page=page,
            name="测试站点",
            url="https://目标站点.com"  # 替换为实际URL
        )

        # 3. 后续操作（例如验证登录状态）
        print("页面标题：", page.title())

        # 4. 关闭资源
        context.close()
        browser.close()

