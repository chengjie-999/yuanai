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
            return "✅ 浏览器已启动"

        self._browser = None
        BrowserInitializer._instance = None

        self._browser = MyWebBrowser(BrowserInitializer().create_driver())
        return "✅ 新浏览器窗口已启动"

    def stop(self) -> str:
        if self._browser:
            try:
                self._browser.close_browser()
            except Exception:
                pass
            self._browser = None
        return "✅ 浏览器已关闭"

    def get_driver(self):
        if not self._browser:
            return None
        if not self._alive():
            self._browser = None
            return None
        return self._browser

    def _alive(self) -> bool:
        """轻量检测浏览器是否存活"""
        if not self._browser:
            return False
        try:
            self._browser.driver.current_url
            return True
        except Exception:
            return False

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
