from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from xiaoyuan_audit.handlers.base_audit import BaseAnswerAuditHandler


class CopyGraphicAnswerAuditHandler(BaseAnswerAuditHandler):
    """抄写图形题-补答审核 专用处理器"""

    def __init__(self, web_driver: WebDriver):
        super().__init__(web_driver)

    def process_task(self, task_name, true='1', **kwargs):
        """处理抄写图形题-补答审核任务"""
        if '抄写图形题-补答审核' not in task_name:
            return

        # 选择审核结果（正确/错误）
        radio_btns = self.find_elements_safely((By.CSS_SELECTOR, '.ant-radio-input'))
        if not radio_btns:
            return

        target_radio_idx = 0 if true else 1
        if len(radio_btns) > target_radio_idx:
            radio_btns[target_radio_idx].click()

        # 点击提交按钮
        submit_btns = self.find_elements_safely((By.CSS_SELECTOR, '.ant-btn-primary'))
        if submit_btns:
            submit_btns[-1].click()  # 点击最后一个主按钮
        print('抄写图形题-补答审核完成')