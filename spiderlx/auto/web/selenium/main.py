from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver

from spiderlx.anti.cookie.selenium import get_cookie, use_cookie
from spiderlx.core.save.urls import web_urls
from webdrivermanager_cn import ChromeDriverManagerAliMirror


# ====================== 第一类：浏览器底层驱动初始化（底层模块）======================
class BrowserInitializer:
    """
    浏览器驱动初始化工具类
    职责：仅负责 Chrome 驱动创建、反爬配置、接管模式配置
    不包含任何页面操作与业务逻辑，纯底层工具
    """

    def __init__(self):
        self.driver = None
        self.options = None

    def _driver_anti_crawl_options(self):
        """
        配置【全新启动】浏览器的反爬参数
        用于：Selenium 自主启动浏览器，非接管模式
        """
        chrome_options = Options()

        # 模拟真实浏览器 UA
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        # 反爬核心：隐藏 Selenium 自动化特征
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        self.options = chrome_options

    def _attach_to_browser_at_port(self):
        """
        配置【接管已有浏览器】的参数（9222 端口）
        用于：连接手动启动的 Chrome，不重新创建浏览器
        注意：接管模式下禁止添加启动类参数，否则会报错
        """
        chrome_options = Options()

        # 核心：接管手动启动的 9222 调试端口
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

        # 接管模式下仅保留必要配置
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument("--disable-dev-shm-usage")

        self.options = chrome_options

    def create_driver(self):
        """
        创建【全新启动】的浏览器驱动（带反爬）
        :return: Chrome 驱动实例
        """
        self._driver_anti_crawl_options()

        try:
            driver = Chrome(
                service=Service(ChromeDriverManagerAliMirror().install()),
                options=self.options
            )
            driver.maximize_window()
            print("✅ 浏览器启动完成（反爬已配置）")
            return driver
        except Exception as e:
            print(f"❌ 浏览器启动失败: {str(e)}")
            raise

    def create_browser(self):
        """
        创建【接管模式】浏览器驱动（连接 9222 端口）
        :return: Chrome 驱动实例（连接已打开浏览器）
        """
        self._attach_to_browser_at_port()

        try:
            driver = Chrome(
                service=Service(ChromeDriverManagerAliMirror().install()),
                options=self.options
            )
            print("✅ 浏览器连接完成（已接管 9222 端口）")
            return driver
        except Exception as e:
            print(f"❌ 浏览器连接失败: {str(e)}")
            raise


# ====================== 第二类：页面业务操作类（上层模块）======================
class MyWebBrowser:
    """
    浏览器业务操作类
    依赖外部传入的 driver，负责页面访问、Cookie、数据解析、页面控制
    """

    def __init__(self, driver: WebDriver):
        self.driver = driver  # 已初始化的浏览器驱动
        self.website_info = {}
        self.current_website_name = None
        self._load_website_info()

    def _load_website_info(self):
        """加载配置文件中的网站信息"""
        self.website_info = {}
        code = 0
        for web in web_urls:
            for name in web:
                self.website_info[code] = name
            code += 1
        print('\n📋 支持网站：', self.website_info)
        print("✅ 网站信息加载完成\n")

    def open_website(self, code=None, name=None, url=None):
        """
        打开指定网站
        :param code: 网站编号
        :param name: 网站名称
        :param url: 自定义网址
        :return: 当前网站名称
        """
        if not self.driver:
            raise RuntimeError("浏览器未初始化")

        target_url = None
        self.current_website_name = None

        # 根据编号打开
        if code is not None:
            code = int(code)
            if code not in self.website_info:
                raise ValueError(f"无效网站编号：{code}")
            self.current_website_name = self.website_info[code]
            target_url = web_urls[code][self.current_website_name][1][0]

        # 根据名称打开
        elif name:
            for idx, website in enumerate(web_urls):
                if name in website:
                    self.current_website_name = name
                    target_url = website[name][1][0]
                    break
            if not target_url:
                raise ValueError(f"未找到网站：{name}")

        # 根据URL打开
        elif url:
            self.current_website_name = "未命名网站"
            target_url = url

        else:
            raise ValueError("必须传入 code / name / url")

        print(f"🌐 访问：{self.current_website_name} | {target_url}")

        self.driver.get(target_url)
        self._verify_loaded()
        return self.current_website_name

    def _verify_loaded(self):
        """验证页面是否正常加载"""
        title = self.driver.title
        if self.current_website_name in title:
            print(f"✅ 【{self.current_website_name}】打开成功")
        else:
            print(f"⚠️ 页面标题：{title}，可能加载异常")

    def get_current_url(self):
        """获取当前页面URL"""
        return self.driver.current_url

    def use_cookies(self):
        """加载并使用本地Cookie"""
        return use_cookie(self.driver, self.current_website_name, self.get_current_url())

    def get_cookies(self):
        """保存当前页面Cookie到本地"""
        return get_cookie(self.driver, self.current_website_name)

    def parse_website_data(self):
        """页面数据解析（可扩展业务逻辑）"""
        try:
            if self.current_website_name == "小猿众包":
                print("📊 开始解析小猿众包数据...")
        except Exception as e:
            print(f"❌ 解析失败：{e}")

    def refresh(self):
        """刷新当前页面"""
        print("🔄 刷新页面")
        self.driver.refresh()
        return True

    def close_browser(self):
        """
        关闭浏览器
        注意：接管模式下仅断开连接，不会关闭真实浏览器
        """
        if self.driver:
            self.driver.quit()
            print("🔌 浏览器连接已关闭")
            self.driver = None


# ====================== AI 调用工具函数（对外接口）======================
def get_driver():
    """
    AI 工具函数：获取【全新启动】的浏览器操作实例
    用途：全新打开浏览器，自动处理驱动、反爬
    :return: MyWebBrowser 业务操作实例
    """
    return MyWebBrowser(BrowserInitializer().create_driver())


def get_browser():
    """
    AI 工具函数：获取【接管模式】浏览器操作实例（连接 9222 端口）
    用途：接管已手动打开的 Chrome，不重启浏览器
    :return: MyWebBrowser 业务操作实例
    """
    # 已修复：原代码错误调用 create_driver，现改为接管模式
    return MyWebBrowser(BrowserInitializer().create_browser())


# ====================== 主程序入口 ======================
def main():
    # 使用接管模式
    browser = get_browser()

    try:
        browser.open_website(code=0)
        browser.parse_website_data()
        input("\n运行结束，按回车断开控制...")
    except Exception as e:
        print(f"❌ 运行出错：{e}")
    finally:
        browser.close_browser()


if __name__ == "__main__":
    main()