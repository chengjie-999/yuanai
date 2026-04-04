from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver

from spiderlx.anti.cookie.selenium import get_cookie, use_cookie
from spiderlx.core.save.urls import urls   # 替换为下方 urls
from webdrivermanager_cn import ChromeDriverManagerAliMirror


# ====================== 第一类：浏览器底层驱动初始化（底层模块）======================
class BrowserInitializer:
    """
    浏览器驱动初始化工具类（单例模式）
    职责：仅负责 Chrome 驱动创建、反爬配置、接管模式配置
    不包含任何页面操作与业务逻辑，纯底层工具
    """
    _instance = None      # 单例实例

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 避免重复初始化属性
        if not hasattr(self, '_initialized'):
            self.driver = None
            self.options = None
            self._initialized = True

    def _driver_anti_crawl_options(self):
        """
        配置【全新启动】浏览器的反爬参数
        用于：Selenium 自主启动浏览器，非接管模式
        """
        chrome_options = Options()

        # 模拟真实浏览器 UA
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36 '
        )

        # 反爬核心：隐藏 Selenium 自动化特征
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        self.options = chrome_options

    def create_driver(self):
        """
        创建【全新启动】的浏览器驱动（带反爬），单例模式，只创建一次
        :return: Chrome 驱动实例
        """
        # 如果已有有效驱动，直接复用
        if self.driver is not None:
            try:
                # 尝试获取 session_id，若异常则驱动失效
                if self.driver.session_id:
                    print("♻️ 使用现有浏览器驱动")
                    return self.driver
            except:
                self.driver = None

        # 创建新驱动
        self._driver_anti_crawl_options()

        try:
            driver = Chrome(
                service=Service(ChromeDriverManagerAliMirror().install()),
                options=self.options
            )
            driver.maximize_window()
            print("✅ 浏览器启动完成（反爬已配置）")
            self.driver = driver
            return driver
        except Exception as e:
            print(f"❌ 浏览器启动失败: {str(e)}")
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
        self.target_url = None
        self._load_website_info()

    def _load_website_info(self):
        """加载配置文件中的网站信息（基于 urls）"""
        self.website_info = {code: item['name'] for code, item in enumerate(urls)}
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

        # 根据编号打开
        if code is not None:
            code = int(code)
            if code not in self.website_info:
                raise ValueError(f"无效网站编号：{code}")
            self.current_website_name = self.website_info[code]
            self.target_url = urls[code]['url'][0]  # 取第一个URL

        # 根据名称打开
        elif name:
            for item in urls:
                if item['name'] == name:
                    self.current_website_name = name
                    self.target_url = item['url'][0]  # 取第一个URL
                    break
            if not self.target_url:
                raise ValueError(f"未找到网站：{name}")

        # 根据URL打开
        elif url:
            self.current_website_name = "未命名网站"
            self.target_url = url

        else:
            raise ValueError("必须传入 code / name / url")

        print(f"🌐 访问：{self.current_website_name} | {self.target_url}")

        self.driver.get(self.target_url)
        return self.current_website_name, self.target_url

    def get_current_url(self):
        """获取当前页面URL"""
        return self.driver.current_url

    def use_cookies(self):
        """加载并使用本地Cookie"""
        return use_cookie(self.driver, self.current_website_name, self.target_url)

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


# ====================== 主程序入口 ======================
def main():
    browser = MyWebBrowser(BrowserInitializer().create_driver())

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
