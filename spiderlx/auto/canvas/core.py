import time
import logging

logger = logging.getLogger(__name__)

CANVAS_CENTER_X = 1000
CANVAS_CENTER_Y = 600

# Selenium 画布选择器（小猿众包 OpenLayers 画布容器）
CANVAS_CSS = ".ol-viewport"


def _selenium_scroll(driver, direction: str, amount: int) -> bool:
    """使用 JS wheel 事件在画布上滚动（OpenLayers 原生支持，无需鼠标）"""
    from selenium.webdriver.common.by import By
    try:
        canvas = driver.find_element(By.CSS_SELECTOR, CANVAS_CSS)
        delta_y = -amount if direction == "down" else amount
        driver.execute_script("""
            arguments[0].dispatchEvent(new WheelEvent('wheel', {
                deltaY: arguments[1],
                deltaMode: 0,
                bubbles: true,
                cancelable: true
            }));
        """, canvas, delta_y)
        time.sleep(0.3)
        return True
    except Exception as e:
        logger.warning("Selenium 画布滚动失败: %s", e)
        return False


def _selenium_click(driver, x: int, y: int) -> bool:
    """使用 JS 在画布指定坐标派发 click 事件（支持无头模式）"""
    try:
        driver.execute_script("""
            var el = document.elementFromPoint(arguments[0], arguments[1]);
            if (el) {
                el.dispatchEvent(new MouseEvent('click', {
                    bubbles: true,
                    cancelable: true,
                    view: window
                }));
            }
        """, x, y)
        time.sleep(0.3)
        return True
    except Exception as e:
        logger.warning("Selenium 画布点击失败: %s", e)
        return False


def _pyautogui_scroll(direction: str, amount: int, x: int = None, y: int = None) -> bool:
    """PyAutoGUI 物理滚动（fallback，需要真实显示器）"""
    try:
        import pyautogui
        cx = x or CANVAS_CENTER_X
        cy = y or CANVAS_CENTER_Y
        scroll_num = -amount if direction == "down" else amount
        pyautogui.moveTo(cx, cy, duration=0.2)
        time.sleep(0.1)
        pyautogui.scroll(clicks=scroll_num, x=cx, y=cy)
        time.sleep(0.2)
        return True
    except Exception as e:
        logger.error("PyAutoGUI 画布滚动失败: %s", e)
        return False


def _pyautogui_click(x: int, y: int) -> bool:
    """PyAutoGUI 物理点击（fallback，需要真实显示器）"""
    try:
        import pyautogui
        pyautogui.moveTo(x, y, duration=0.2)
        time.sleep(0.1)
        pyautogui.click()
        time.sleep(0.3)
        return True
    except Exception as e:
        logger.error("PyAutoGUI 画布点击失败: %s", e)
        return False


def scroll(direction: str = "down", amount: int = 1000, driver=None, x: int = None, y: int = None) -> bool:
    """
    画布滚动。优先使用 Selenium ActionChains（支持无头），失败回退到 PyAutoGUI。
    参数 driver: Selenium WebDriver 实例（传入时优先使用 Selenium）
    """
    if driver is not None:
        if _selenium_scroll(driver, direction, amount):
            return True
        logger.info("Selenium 画布滚动失败，回退到 PyAutoGUI")
    return _pyautogui_scroll(direction, amount, x, y)


def click(x: int, y: int, driver=None) -> bool:
    """
    画布点击。优先使用 Selenium ActionChains（支持无头），失败回退到 PyAutoGUI。
    参数 driver: Selenium WebDriver 实例（传入时优先使用 Selenium）
    """
    if driver is not None:
        if _selenium_click(driver, x, y):
            return True
        logger.info("Selenium 画布点击失败，回退到 PyAutoGUI")
    return _pyautogui_click(x, y)


def click_center(driver=None) -> bool:
    """点击画布中心"""
    return click(CANVAS_CENTER_X, CANVAS_CENTER_Y, driver=driver)
