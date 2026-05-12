import atexit
import logging
import threading

from spiderlx.auto.web.selenium.main import MyWebBrowser, BrowserInitializer

logger = logging.getLogger(__name__)


class BrowserManager:
    """浏览器管理器（单例），统一管理 Chrome 驱动生命周期，带健康检查与线程安全"""

    _instance = None
    _singleton_lock = threading.Lock()
    _atexit_registered = False

    def __new__(cls):
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._browser = None
                    cls._instance._raw_driver = None
                    cls._instance._op_lock = threading.Lock()
        return cls._instance

    # ———————— 进程清理 ————————

    @classmethod
    def _ensure_atexit(cls):
        if not cls._atexit_registered:
            atexit.register(cls._atexit_cleanup)
            cls._atexit_registered = True

    @classmethod
    def _atexit_cleanup(cls):
        inst = cls._instance
        if inst is None:
            return
        driver = inst._raw_driver
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        inst._raw_driver = None
        inst._browser = None

    # ———————— 核心操作 ————————

    def start(self) -> str:
        with self._op_lock:
            if self._browser and self._alive():
                logger.info("浏览器重用现有实例")
                return "✅ 浏览器已启动"

            self._force_cleanup()

            logger.info("创建新浏览器实例...")
            driver = BrowserInitializer().create_driver()
            self._raw_driver = driver
            self._browser = MyWebBrowser(driver)
            self._ensure_atexit()
            logger.info("浏览器创建成功")
            return "✅ 新浏览器窗口已启动"

    def stop(self) -> str:
        with self._op_lock:
            if self._browser:
                try:
                    logger.info("正在关闭浏览器...")
                    self._browser.close_browser()
                    logger.info("浏览器已关闭")
                except Exception as e:
                    logger.warning("关闭浏览器异常: %s", e)
                finally:
                    self._raw_driver = None
                    self._browser = None
            return "✅ 浏览器已关闭"

    def _force_cleanup(self):
        """强制清理旧驱动（包括残留的 Chrome 进程）"""
        if self._raw_driver is not None:
            try:
                self._raw_driver.quit()
            except Exception:
                pass
            self._raw_driver = None
        self._browser = None

    def _alive(self) -> bool:
        if not self._browser or not self._raw_driver:
            return False
        try:
            self._raw_driver.current_url
            return True
        except Exception as e:
            logger.warning("浏览器检测失效: %s", e)
            self._force_cleanup()
            return False

    def get_driver(self):
        if not self._browser:
            return None
        if not self._alive():
            return None
        return self._browser

    def set_browser(self, browser):
        """注入外部浏览器实例（Streamlit 等自行管理生命周期的场景）"""
        with self._op_lock:
            self._browser = browser
            self._raw_driver = browser.driver if browser else None
            if browser:
                self._ensure_atexit()

    @property
    def running(self) -> bool:
        return self._browser is not None and self._raw_driver is not None and self._alive()

    @property
    def current_url(self) -> str:
        if not self._browser or not self._raw_driver:
            return ""
        try:
            return self._raw_driver.current_url
        except Exception:
            return ""

    @property
    def current_title(self) -> str:
        if not self._browser or not self._raw_driver:
            return ""
        try:
            return self._raw_driver.title
        except Exception:
            return ""

    def screenshot(self) -> bytes:
        with self._op_lock:
            if not self._browser or not self._raw_driver:
                raise RuntimeError("浏览器未启动")
            if not self._alive():
                raise RuntimeError("浏览器已断开")
            return self._raw_driver.get_screenshot_as_png()


browser_manager = BrowserManager()
