import base64
import time
from abc import ABC, abstractmethod
from selenium.common import WebDriverException, NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from xiaoyuan_audit.base.task_card_base import BaseTaskCardHandler
from utils.data_path import img_save_path


class BaseAnswerAuditHandler(BaseTaskCardHandler, ABC):
    """答案审核基础类：定义审核任务的通用接口"""

    def __init__(self, web_driver: WebDriver):
        super().__init__(web_driver)

    @abstractmethod
    def process_task(self, task_name, **kwargs):
        """处理具体任务（子类必须实现）"""
        pass

    def resize_question(self, down=True, count=6):
        """调整题目大小（单题标答审核专用）"""
        if not down:
            return

        down_buttons = self.find_elements_safely((By.CSS_SELECTOR, '.ol-zoom-out'))
        if not down_buttons:
            return

        down_button = down_buttons[0]
        for _ in range(count):
            down_button.click()
            time.sleep(0.05)

    def restore_question_size(self):
        """恢复题目原始大小"""
        restore_buttons = self.find_elements_safely((By.CSS_SELECTOR, '.ol-control'))
        if len(restore_buttons) >= 4:
            try:
                restore_buttons[3].click()
                return True
            except Exception:
                return False
        return False

    def capture_question_info(self, screenshot=True):
        """捕获题目信息（参考答案、标记答案截图）"""
        qa = []

        # 获取参考答案图片
        refer_img_elem = self.find_element_safely((By.CSS_SELECTOR, '.ant-image > img'))
        if refer_img_elem:
            refer_img_src = refer_img_elem.get_attribute('src')
            qa.append(refer_img_src)

        # 截图题目和答案
        if screenshot:
            question_elem = self.find_element_safely((By.CSS_SELECTOR, '.ol-viewport'))
            if not question_elem:
                return qa

            # 独立标记答案截图
            independent_answer_loc = (By.CSS_SELECTOR, ".yst-mathjax-loading")
            independent_img_path = img_save_path('独立.png')
            try:
                independent_answer_elem = question_elem.find_element(*independent_answer_loc)
                independent_answer_elem.screenshot(independent_img_path)
            except NoSuchElementException:
                pass
            qa.append(independent_img_path)

            # 批量答案截图
            answer_elems = question_elem.find_elements(By.CSS_SELECTOR, '.ol-overlay-container')
            for i, answer_elem in enumerate(answer_elems):
                try:
                    answer_img_path = img_save_path(f'答案{i}.png')
                    answer_elem.screenshot(answer_img_path)
                    qa.append(answer_img_path)
                except WebDriverException:
                    continue

        return qa