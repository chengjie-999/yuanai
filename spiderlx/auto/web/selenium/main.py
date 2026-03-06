from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager

from spiderlx.core.save.urls import web_urls
from spiderlx.anti.cookie import selenium
# 安装：pip install webdrivermanager-cn
from webdrivermanager_cn import ChromeDriverManagerAliMirror


class WebBrowser:
    """
    封装Selenium Chrome浏览器操作的面向对象类
    提供浏览器初始化、网站管理、页面访问等功能
    创建对象时自动初始化浏览器并加载网站信息
    """

    def __init__(self):
        """初始化浏览器对象，自动完成浏览器配置和网站信息加载"""
        self.driver = None  # 浏览器驱动实例
        self.option = None
        self.website_info = {}  # 支持的网站信息缓存
        self.current_website_name = None  # 当前打开的网站名称

        # 创建对象时自动执行：初始化浏览器 + 加载网站信息
        self._configure_chrome_options()
        self._initialize_browser()
        self._load_website_info()

    def _configure_chrome_options(self):
        """私有方法：配置Chrome浏览器选项（封装配置逻辑）"""
        chrome_options = Options()

        # 添加真实User-Agent，模拟正常浏览器
        chrome_options.add_argument(
            'user-agent='
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        # 禁用自动化检测相关配置（反爬关键）
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        self.option = chrome_options

    def _initialize_browser(self):
        """私有方法：初始化Chrome浏览器（整合到__init__中）"""
        try:
            # 创建Chrome驱动
            self.driver = Chrome(
                service=Service(ChromeDriverManagerAliMirror().install()),
                options=self.option
            )
            self.driver.maximize_window()
            print("✅ 浏览器初始化成功")
        except Exception as e:
            print(f"❌ 浏览器初始化失败: {str(e)}")
            raise

    def _load_website_info(self):
        """私有方法：加载并缓存支持的网站信息（整合到__init__中）"""
        self.website_info = {}
        code = 0
        for web in web_urls:
            for name in web:
                self.website_info[code] = name
            code += 1

        print('\n📋 现支持的网站信息如下————')
        print(self.website_info)
        print("✅ 网站信息加载成功\n")

    def open_website(self, code=None, name=None, url=None):
        """
        打开指定的网站
        :param code: 网站编号
        :param name: 网站名称
        :param url: 手动输入的网站URL
        :return: 打开的网站名称
        """
        if not self.driver:
            raise RuntimeError("浏览器初始化失败，无法打开网站")

        target_url = None
        self.current_website_name = None

        # 根据不同参数获取目标URL
        if code is not None:
            code = int(code)
            if code not in self.website_info:
                raise ValueError(f"无效的网站编号: {code}")
            self.current_website_name = self.website_info[code]
            target_url = web_urls[code][self.current_website_name][1][0]

        elif name:
            for idx, website in enumerate(web_urls):
                if name in website.keys():
                    self.current_website_name = name
                    target_url = website[name][1][0]
                    break
            if not target_url:
                raise ValueError(f"未找到名称为【{name}】的网站")

        elif url:

            self.current_website_name = '未命名网站'
            target_url = url

        else:
            raise ValueError("必须提供code、name或url中的一个参数")

        # 访问目标URL
        print(f"🌐 正在访问: {self.current_website_name} - {target_url}")
        self.driver.get(target_url)

        # 处理Cookie/登录问题（仅针对命名网站）
        if self.current_website_name != '未命名网站':
            selenium.use_cookie(self.driver, self.current_website_name, target_url)

        # 验证网站是否成功加载
        self._verify_website_loaded()

        return self.current_website_name

    def _verify_website_loaded(self):
        """私有方法：验证网站是否成功加载"""
        page_title = self.driver.title
        if self.current_website_name in page_title:
            print(f'✅ 【{self.current_website_name}】网站已成功打开！！！')
        else:
            print(f'⚠️ 警告：【{self.current_website_name}】可能未正常加载，页面标题: {page_title}')

    def get_current_url(self):
        """获取当前页面的URL"""
        if not self.driver:
            raise RuntimeError("浏览器未初始化")
        return self.driver.current_url

    def parse_website_data(self):
        """解析网站数据（可根据不同网站扩展）"""
        try:
            if self.current_website_name == '小猿众包':
                # 这里可以添加小猿众包的解析逻辑
                print("📊 开始解析小猿众包数据...")
                # 示例：可添加具体的解析代码
        except Exception as e:
            print(f"❌ 解析数据时出错: {str(e)}")

    def close_browser(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            print("🔌 浏览器已关闭")
            self.driver = None


def main():
    """程序主入口"""
    # 创建浏览器实例（自动初始化浏览器 + 加载网站信息）
    print("🚀 正在创建浏览器实例...")
    browser = WebBrowser()

    try:
        # 直接打开网站（无需手动初始化浏览器和加载信息）
        # 示例：browser.open_website(code=0) 或 browser.open_website(name="小猿众包")
        browser.open_website(code=0)  # 这里替换成你要访问的网站编号/名称/URL

        # 解析网站数据
        browser.parse_website_data()

        input('\n运行结束，按回车关闭浏览器...')

    except Exception as e:
        print(f"❌ 程序执行出错: {str(e)}")
    finally:
        # 确保浏览器最终关闭
        browser.close_browser()


if __name__ == "__main__":
    main()
