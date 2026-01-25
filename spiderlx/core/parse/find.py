from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By


def xpath(web_driver, value):
    ele = web_driver.find_elements(by=By.XPATH, value=value)
    return ele


def css(web_driver: WebDriver, value):
    pass
    return
