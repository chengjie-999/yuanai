import time
from selenium.common import NoSuchElementException, ElementNotInteractableException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from xiaoyuan_audit.handlers.base_audit import BaseAnswerAuditHandler


class SingleAnswerAuditHandler(BaseAnswerAuditHandler):
    """单题标答-审核 专用处理器"""

    def __init__(self, web_driver: WebDriver):
        super().__init__(web_driver)

    def process_task(self, task_name, true='1', up=False, **kwargs):
        """处理单题标答审核任务"""
        if '单题标答-审核' not in task_name:
            return

        # 放大/缩小题目
        if up:
            self.resize_question()
            time.sleep(1)

        # 处理独立答案
        question_elem = self.find_element_safely((By.CSS_SELECTOR, '.ol-viewport'))
        if not question_elem:
            return

        self._process_independent_answer(question_elem)
        # 处理批改答案
        self._process_corrected_answer(question_elem)

        # 恢复题目大小
        if up:
            self.restore_question_size()

    def _process_independent_answer(self, question_elem):
        """处理独立批改答案"""
        try:
            answer_elem = question_elem.find_element(By.CSS_SELECTOR, ".yst-mathjax-loading")
            ActionChains(self.web_driver).move_to_element(answer_elem).perform()
            answer_elem.click()
            print(f"独立答案文本: {answer_elem.text}")
            time.sleep(0.5)

            # 点击正确按钮
            true_btn = question_elem.find_element(By.CSS_SELECTOR, '.button_gjJ0I')
            true_btn.click()
            print('独立答案判断完成')
        except NoSuchElementException:
            print("未找到【独立批改答案】，已跳过")
        except ElementNotInteractableException:
            print('【独立批改答案】交互隐藏！')

    def _process_corrected_answer(self, question_elem):
        """处理批改答案（黄框）"""
        try:
            ActionChains(self.web_driver).move_to_element(question_elem).perform()

            # 遍历所有批改答案并标记正确
            answer_elems = question_elem.find_elements(By.CSS_SELECTOR, '.ol-overlay-container')
            if not answer_elems:
                print("未找到【批改答案】，已跳过")
                return

            true_btn = question_elem.find_element(By.CSS_SELECTOR, '.button_3sIPu')
            for _ in answer_elems:
                true_btn.click()

            print('答案判断完成！')
        except NoSuchElementException:
            print("未找到【批改答案】，已跳过")
        except ElementNotInteractableException as e:
            print(f'【批改答案】交互隐藏！{e.msg}')
        except Exception as e:
            print(f"处理批改答案异常: {e}")