from selenium import webdriver
from selenium.webdriver.common.by import By
import time

from spiderlx.auto.web.selenium.main import chrome


def highlight_elements(driver, elements=None, element=None, duration=3):
    """
    高亮标记找到的元素（修复 JS 语法错误）
    :param element:
    :param driver: WebDriver 实例
    :param elements: find_elements 返回的元素列表
    :param duration: 高亮持续时间（秒），默认 3 秒
    """
    original_styles = []
    if elements:
        for elem in elements:
            if elem.is_displayed():  # 只标记可见元素
                # 记录原始样式（简化 JS 代码，避免换行）
                original_style = driver.execute_script("return arguments[0].getAttribute('style');", elem)
                original_styles.append((elem, original_style))

                # 修复：将多行 JS 改为单行，用分号分隔样式，避免语法错误
                driver.execute_script(
                    "arguments[0].setAttribute('style', 'border: 3px solid red !important; background-color: rgba("
                    "255, 0, "
                    "0, 0.2) !important; z-index: 9999 !important;');",
                    elem
                )
    if element:
        if element.is_displayed():  # 只标记可见元素
            # 记录原始样式（简化 JS 代码，避免换行）
            original_style = driver.execute_script("return arguments[0].getAttribute('style');", element)
            original_styles.append((element, original_style))

            # 修复：将多行 JS 改为单行，用分号分隔样式，避免语法错误
            driver.execute_script(
                "arguments[0].setAttribute('style', 'border: 3px solid red !important; background-color: rgba("
                "255, 0, "
                "0, 0.2) !important; z-index: 9999 !important;');",
                element
            )

    time.sleep(duration)  # 保持高亮

    # 恢复原始样式
    for elem, original_style in original_styles:
        if original_style is None:
            driver.execute_script("arguments[0].removeAttribute('style');", elem)
        else:
            driver.execute_script("arguments[0].setAttribute('style', arguments[1]);", elem, original_style)


# 示例运行
if __name__ == "__main__":
    # 注意：Selenium 4.10+ 不需要手动下载驱动（自动管理）
    driver = chrome()
    driver.get("https://www.baidu.com")
    driver.maximize_window()  # 最大化窗口，方便查看标记

    # 定位所有 a 标签（可替换为其他定位方式）
    elements = driver.find_elements(By.TAG_NAME, "a")

    # 高亮标记（持续 3 秒）
    highlight_elements(driver, elements, duration=30)

    driver.quit()
