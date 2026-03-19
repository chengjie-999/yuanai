from selenium.webdriver.chrome.webdriver import WebDriver

from xiaoyuan_audit.handlers.single_answer import SingleAnswerAuditHandler
from xiaoyuan_audit.handlers.correction_answer import CorrectionAnswerAuditHandler
from xiaoyuan_audit.handlers.copy_graphic import CopyGraphicAnswerAuditHandler


class XiaoYuanAnswerAuditSystem:
    """小猿众包答案审核系统：整合所有处理器，对外提供统一接口"""

    def __init__(self, web_driver: WebDriver):
        self.web_driver = web_driver
        # 初始化各任务处理器
        self.single_answer_handler = SingleAnswerAuditHandler(web_driver)
        self.correction_handler = CorrectionAnswerAuditHandler(web_driver)
        self.copy_graphic_handler = CopyGraphicAnswerAuditHandler(web_driver)

    def find_target_task(self, target_keyword='单题标答-审核'):
        """查找目标任务卡片"""
        return self.single_answer_handler.find_task_cards(target_keyword)

    def start_target_task(self, task_card):
        """启动目标任务"""
        return self.single_answer_handler.start_task(task_card)

    def process_task_by_name(self, task_name, **kwargs):
        """根据任务名分发到对应处理器"""
        if '单题标答-审核' in task_name:
            self.single_answer_handler.process_task(task_name, **kwargs)
        elif '3.0改错-补答' in task_name:
            self.correction_handler.process_task(task_name, **kwargs)
        elif '抄写图形题-补答审核' in task_name:
            self.copy_graphic_handler.process_task(task_name, **kwargs)
        else:
            print(f"未找到{task_name}对应的处理器")

    def get_task_question_info(self):
        """获取题目信息"""
        return self.single_answer_handler.capture_question_info()

    def submit_current_task(self, status, cause=None):
        """提交当前任务"""
        return self.single_answer_handler.submit_task(status, cause)