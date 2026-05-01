import time

import pyautogui

CANVAS_CENTER_X = 1000
CANVAS_CENTER_Y = 600


def scroll(direction: str = "down", amount: int = 1000, x: int = None, y: int = None) -> bool:
    """
    PyAutoGUI 物理操作画布滚动。
    只动 canvas 内部，不滚页面。
    参数 direction: 'down' 向下 / 'up' 向上
    参数 amount: 滚动量（默认1000）
    参数 x, y: 画布中心坐标（可选）
    """
    try:
        cx = x or CANVAS_CENTER_X
        cy = y or CANVAS_CENTER_Y
        scroll_num = -amount if direction == "down" else amount
        pyautogui.moveTo(cx, cy, duration=0.2)
        time.sleep(0.1)
        pyautogui.scroll(clicks=scroll_num, x=cx, y=cy)
        time.sleep(0.2)
        return True
    except Exception as e:
        print(f"❌ 画布滚动失败: {e}")
        return False


def click(x: int, y: int) -> bool:
    """
    PyAutoGUI 物理点击画布指定坐标。
    参数 x, y: 屏幕坐标
    """
    try:
        pyautogui.moveTo(x, y, duration=0.2)
        time.sleep(0.1)
        pyautogui.click()
        time.sleep(0.3)
        return True
    except Exception as e:
        print(f"❌ 画布点击失败: {e}")
        return False


def click_center() -> bool:
    """点击画布中心"""
    return click(CANVAS_CENTER_X, CANVAS_CENTER_Y)
