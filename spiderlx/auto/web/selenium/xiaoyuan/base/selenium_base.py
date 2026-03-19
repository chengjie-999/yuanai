import time
from selenium.common import NoSuchElementException, ElementNotInteractableException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from spiderlx.core.save.save_data import SavedData


class BaseSeleniumOperation:
    """基础Selenium操作类：封装所有任务通用的浏览器操作"""

    def __init__(self, web_driver: WebDriver):
        self.web_driver = web_driver
        self.wait = WebDriverWait(self.web_driver, 30)  # 统一等待配置

    def get_html(self):
        """获取当前页面HTML并保存"""
        html = self.web_driver.page_source
        print(html)
        sd = SavedData(f'小猿')
        sd.save_data_html(html)

    def click_element_safely(self, locator: tuple, action_before_click=None):
        """安全点击元素：封装通用点击逻辑，减少重复代码"""
        try:
            element = self.wait.until(EC.visibility_of_element_located(locator))
            if action_before_click:
                action_before_click(element)
            element.click()
            return True
        except (NoSuchElementException, ElementNotInteractableException) as e:
            print(f"元素点击失败: {e}")
            return False

    def find_element_safely(self, locator: tuple):
        """安全查找元素，返回元素或None"""
        try:
            return self.wait.until(EC.visibility_of_element_located(locator))
        except NoSuchElementException:
            return None

    def find_elements_safely(self, locator: tuple):
        """安全查找元素列表，返回列表或空列表"""
        try:
            return self.wait.until(EC.visibility_of_all_elements_located(locator))
        except NoSuchElementException:
            return []

    def go_back_to_homepage(self):
        """返回小猿众包首页"""
        home_locator = (By.CSS_SELECTOR, '.ant-menu-item')
        self.click_element_safely(home_locator)
        print('回首页')
        return True

    def handle_task_modal(self, go_on=True):
        """处理任务消息提示框（通用弹窗处理）"""
        try:
            time.sleep(1)
            box = self.find_element_safely((By.CSS_SELECTOR, '.ant-modal-content'))
            if not box:
                print('任务充足，无弹窗')
                return go_on

            message = box.find_element(By.CSS_SELECTOR, '.ant-modal-confirm-title').text
            print(f"弹窗消息: {message}")

            # 处理「继续认领下一包」弹窗
            if message == '当前任务包已处理完毕，是否继续认领下一包？' and go_on:
                confirm_btn = box.find_element(By.CSS_SELECTOR, '.ant-modal-confirm-btns .ant-btn-primary')
                confirm_btn.click()
                return go_on

            # 处理「知道了」弹窗
            know_btn = box.find_element(By.CSS_SELECTOR, '.ant-modal-confirm-btns')
            know_text = know_btn.text
            print(f"弹窗按钮文本: {know_text}")
            know_btn.click()
            return not go_on if know_text == '知道了' else go_on

        except NoSuchElementException:
            print('无任务提示弹窗')
            return go_on

    def submit_task(self, status, cause=None):
        """提交任务（通用提交逻辑）"""
        foot = self.find_element_safely((By.CSS_SELECTOR, '.container_23Xxj'))
        if not foot:
            return False

        button_locators = {
            '提交领下一任务': (By.CSS_SELECTOR, '.ant-btn'),
            '提交回首页': (By.CSS_SELECTOR, '.ant-btn'),
            '整题驳回': (By.CSS_SELECTOR, '.ant-btn'),
            '默认': (By.CSS_SELECTOR, '.ant-space:nth-child(2) .ant-space-item:nth-child(5) .ant-btn')
        }

        try:
            if status == '提交领下一任务':
                button = foot.find_elements(*button_locators[status])[-1]
            elif status == '提交回首页':
                button = foot.find_element(*button_locators[status])
            elif status == '整题驳回':
                button = foot.find_elements(*button_locators[status])[1]
                # 填写驳回理由
                input_elem = self.find_element_safely((By.CSS_SELECTOR, '.ant-input'))
                if input_elem and cause:
                    input_elem.send_keys(cause)
            else:
                button = self.find_element_safely(button_locators['默认'])

            if button:
                print(f"点击提交按钮: {button.text}")
                button.click()
                time.sleep(0.5)
            return self.handle_task_modal()
        except Exception as e:
            print(f"提交任务失败: {e}")
            return False

    def confirm_rejection(self):
        """确认驳回操作（通用驳回确认）"""
        reject_box = self.find_element_safely((By.CSS_SELECTOR, '.ant-modal-content'))
        if not reject_box:
            return ""

        confirm_btn = reject_box.find_element(By.CSS_SELECTOR, '.ant-btn-primary')
        confirm_text = confirm_btn.text
        confirm_btn.click()
        return confirm_text
