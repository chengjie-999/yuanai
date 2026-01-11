import asyncio
import random
import time
from playwright.async_api import async_playwright

# ===================== 反扒配置项 =====================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/121.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
]

BROWSER_CONFIG = {
    "headless": False,
    "slow_mo": random.randint(100, 300),
    "args": [
        "--start-maximized",
        "--disable-blink-features=AutomationControlled",
        "--disable-extensions",
        "--disable-plugins-discovery",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        f"--user-agent={random.choice(USER_AGENTS)}",
    ],
}

ACTION_CONFIG = {
    "click_delay": (0.5, 2.0),
    "scroll_step": (50, 200),
    "scroll_delay": (0.3, 1.0),
    "page_wait_time": (2, 5),
}


# ===================== 核心逻辑 =====================
async def init_anti_detect_browser(playwright):
    """初始化反检测浏览器"""
    browser = await playwright.chromium.launch(**BROWSER_CONFIG)
    context = await browser.new_context(
        viewport=None,
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
        geolocation={"latitude": 31.230416, "longitude": 121.473701},
        permissions=["geolocation"],
        user_agent=random.choice(USER_AGENTS),
        storage_state=''
    )

    # 注入反检测JS
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.chrome = { app: { isInstalled: false }, runtime: {}, webstore: {} };
        delete window.navigator['$cdc_asdjflasutopfhvcZLmcfl_'];
    """)
    return browser, context


async def simulate_human_behavior(page):
    """模拟真人行为"""
    # 随机停留
    await page.wait_for_timeout(int(random.uniform(*ACTION_CONFIG["page_wait_time"]) * 1000))

    # 随机滚动
    scroll_height = await page.evaluate("document.body.scrollHeight")
    current_scroll = 0
    while current_scroll < scroll_height * 0.7:
        step = random.randint(*ACTION_CONFIG["scroll_step"])
        current_scroll += step
        await page.evaluate(f"window.scrollTo(0, {current_scroll})")
        await page.wait_for_timeout(int(random.uniform(*ACTION_CONFIG["scroll_delay"]) * 1000))

    # 随机点击（容错）
    try:
        selectors = ["a", "button"]
        elements = await page.query_selector_all(random.choice(selectors))
        if elements:
            elem = random.choice(elements)
            await elem.wait_for_element_state("visible", timeout=3000)
            await page.wait_for_timeout(int(random.uniform(*ACTION_CONFIG["click_delay"]) * 1000))
            await elem.click()
    except:
        pass


async def anti_crawl(url):
    """主反扒逻辑（适配旧版Playwright）"""
    async with async_playwright() as playwright:
        browser, context = await init_anti_detect_browser(playwright)
        page = await context.new_page()

        # ========== 关键修改：用page.route()拦截请求（适配旧版Playwright） ==========
        async def handle_route(route, request):
            """拦截所有请求并修改/过滤"""
            # 复制并修改请求头
            headers = request.headers.copy()
            headers.update({
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://www.baidu.com",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
            })

            # 跳过图片/视频/字体请求
            if request.resource_type in ["image", "video", "font"]:
                await route.abort()  # 旧版用route.abort()而非request.abort()
            else:
                await route.continue_(headers=headers)  # 旧版用route.continue_()

        # 拦截所有请求（通配符*）
        await page.route("**/*", handle_route)

        try:
            # 访问页面（重试机制）
            for retry in range(3):
                try:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    break
                except Exception as e:
                    print(f"重试 {retry + 1}/3: {str(e)[:80]}")
                    await page.wait_for_timeout(2000)
            else:
                raise Exception("访问被拦截")

            # 模拟真人行为
            await simulate_human_behavior(page)

            # 输出结果
            print("=" * 50)
            print(f"✅ 访问成功！")
            print(f"页面标题：{await page.title()}")
            print(f"内容长度：{len(await page.inner_text('body'))}")
            print("=" * 50)

        except Exception as e:
            print(f"❌ 执行错误: {e}")
        finally:
            await page.wait_for_timeout(3000)
            await context.close()
            await browser.close()


# ===================== 执行入口 =====================
if __name__ == "__main__":
    TARGET_URL = "https://www.example.com"
    try:
        asyncio.run(anti_crawl(TARGET_URL))
    except AttributeError:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(anti_crawl(TARGET_URL))
        loop.close()
