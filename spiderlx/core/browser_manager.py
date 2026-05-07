from spiderlx.auto.web.selenium.main import MyWebBrowser, BrowserInitializer


class BrowserManager:
    """浏览器管理器（单例），带健康检查"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._browser = None
        return cls._instance

    def start(self) -> str:
        if self._browser and self._alive():
            print("♻️ 浏览器重用现有实例")
            return "✅ 浏览器已启动"

        self._browser = None
        BrowserInitializer._instance = None

        print("🔄 创建新浏览器实例...")
        self._browser = MyWebBrowser(BrowserInitializer().create_driver())
        print("✅ 浏览器创建成功")
        return "✅ 新浏览器窗口已启动"

    def stop(self) -> str:
        if self._browser:
            try:
                print("🔌 正在关闭浏览器...")
                self._browser.close_browser()
                print("✅ 浏览器已关闭")
            except Exception as e:
                print(f"⚠️ 关闭浏览器异常: {e}")
            self._browser = None
        return "✅ 浏览器已关闭"

    def _alive(self) -> bool:
        if not self._browser:
            return False
        try:
            self._browser.driver.current_url
            return True
        except Exception as e:
            print(f"💀 浏览器检测失效: {e}")
            return False

    def get_driver(self):
        if not self._browser:
            return None
        if not self._alive():
            self._browser = None
            return None
        return self._browser

    @property
    def running(self) -> bool:
        return self._browser is not None and self._alive()

    @property
    def current_url(self) -> str:
        if not self._browser:
            return ""
        try:
            return self._browser.driver.current_url
        except Exception:
            return ""

    @property
    def current_title(self) -> str:
        if not self._browser:
            return ""
        try:
            return self._browser.driver.title
        except Exception:
            return ""

    def screenshot(self) -> bytes:
        if not self._browser:
            raise RuntimeError("浏览器未启动")
        return self._browser.driver.get_screenshot_as_png()


browser_manager = BrowserManager()
