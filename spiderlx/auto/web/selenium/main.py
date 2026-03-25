from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from spiderlx.anti.cookie.selenium import get_cookie, use_cookie
from spiderlx.core.save.urls import web_urls
from spiderlx.anti.cookie import selenium
from webdrivermanager_cn import ChromeDriverManagerAliMirror


# ====================== 第一类：只负责【浏览器初始化 + 反爬】======================
class BrowserInitializer:
    """
    独立职责：仅负责 Chrome 浏览器的初始化与反爬配置
    不包含任何页面操作、业务逻辑，纯底层驱动配置
    """

    def __init__(self):
        self.driver = None
        self.options = None

    def _configure_anti_crawl_options(self):
        """配置反爬与浏览器选项（独立功能）"""
        chrome_options = Options()

        # 模拟真实浏览器指纹
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        # 核心反爬配置：隐藏Selenium自动化特征
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        self.options = chrome_options

    def create_driver(self):
        """
        创建并返回浏览器驱动（对外方法）
        :return: driver 实例
        """
        self._configure_anti_crawl_options()

        try:
            driver = Chrome(
                service=Service(ChromeDriverManagerAliMirror().install()),
                options=self.options
            )
            driver.maximize_window()
            print("✅ 浏览器初始化（反爬已配置）")
            return driver
        except Exception as e:
            print(f"❌ 浏览器启动失败: {str(e)}")
            raise


# ====================== 第二类：只负责【页面操作 / 业务逻辑】======================
class MyWebBrowser:
    """
    上层操作类：依赖已初始化的driver
    负责：打开网站、Cookie、解析、刷新、关闭等
    """

    def __init__(self, driver):
        self.driver = driver  # 接收外部传入的已初始化好的driver
        self.website_info = {}
        self.current_website_name = None
        self._load_website_info()

    def _load_website_info(self):
        """加载网站信息"""
        self.website_info = {}
        code = 0
        for web in web_urls:
            for name in web:
                self.website_info[code] = name
            code += 1
        print('\n📋 支持网站：', self.website_info)
        print("✅ 网站信息加载完成\n")

    def open_website(self, code=None, name=None, url=None):
        """打开网站"""
        if not self.driver:
            raise RuntimeError("浏览器未初始化")

        target_url = None
        self.current_website_name = None

        if code is not None:
            code = int(code)
            if code not in self.website_info:
                raise ValueError(f"无效网站编号：{code}")
            self.current_website_name = self.website_info[code]
            target_url = web_urls[code][self.current_website_name][1][0]

        elif name:
            for idx, website in enumerate(web_urls):
                if name in website:
                    self.current_website_name = name
                    target_url = website[name][1][0]
                    break
            if not target_url:
                raise ValueError(f"未找到网站：{name}")

        elif url:
            self.current_website_name = "未命名网站"
            target_url = url

        else:
            raise ValueError("必须传入 code / name / url")

        print(f"🌐 访问：{self.current_website_name} | {target_url}")
        self.driver.get(target_url)

        # 加载Cookie
        if self.current_website_name != "未命名网站":
            r = self.use_cookies()
            if not r:
                print('cookies添加失败！', __name__)
                return False

        self._verify_loaded()
        return self.current_website_name

    def _verify_loaded(self):
        """验证页面是否加载成功"""
        title = self.driver.title
        if self.current_website_name in title:
            print(f"✅ 【{self.current_website_name}】打开成功")
        else:
            print(f"⚠️ 页面标题：{title}，可能加载异常")

    def get_current_url(self):
        return self.driver.current_url

    def use_cookies(self):
        return use_cookie(self.driver, self.current_website_name, self.get_current_url())

    def get_cookies(self):
        return get_cookie(self.driver, self.current_website_name)

    def parse_website_data(self):
        """解析数据（业务扩展）"""
        try:
            if self.current_website_name == "小猿众包":
                print("📊 开始解析小猿众包数据...")
        except Exception as e:
            print(f"❌ 解析失败：{e}")

    def refresh(self):
        """刷新页面"""
        print("🔄 刷新页面")
        self.driver.refresh()
        return True

    def close_browser(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            print("🔌 浏览器已关闭")
            self.driver = None


# ====================== 主程序入口 ======================
def main():
    print("🚀 启动底层浏览器...")

    # 1. 初始化浏览器（反爬 + 驱动）
    initializer = BrowserInitializer()
    driver = initializer.create_driver()

    # 2. 传入driver，创建业务操作对象
    browser = MyWebBrowser(driver)

    try:
        browser.open_website(code=0)
        browser.parse_website_data()
        input("\n运行结束，按回车关闭浏览器...")
    except Exception as e:
        print(f"❌ 运行出错：{e}")
    finally:
        browser.close_browser()


if __name__ == "__main__":
    main()
