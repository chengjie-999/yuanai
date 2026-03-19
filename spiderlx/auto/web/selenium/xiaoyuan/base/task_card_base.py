from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from xiaoyuan_audit.base.selenium_base import BaseSeleniumOperation


class BaseTaskCardHandler(BaseSeleniumOperation):
    """任务卡片处理父类：封装任务卡片查找、开始任务等操作"""

    def __init__(self, web_driver: WebDriver):
        super().__init__(web_driver)

    def find_task_cards(self, target_task_keyword=None):
        """查找任务卡片，支持按关键词筛选"""
        cards = self.find_elements_safely((By.CSS_SELECTOR, ".task-card"))
        title_cards = {}

        for card in cards:
            try:
                # 获取任务标题
                title_elem = card.find_element(By.CSS_SELECTOR, '.task-card-title')
                title = title_elem.text.strip()

                # 获取任务状态
                warn_elem = card.find_element(By.CSS_SELECTOR, '.text-warning:nth-child(2)')
                warn = warn_elem.text
            except Exception:
                warn = '暂无任务'

            full_title = f'{title}【{warn}】'
            print(f"找到任务卡片: {full_title}")
            title_cards[full_title] = card

            # 找到目标任务则提前终止遍历
            if target_task_keyword and target_task_keyword in full_title:
                break

        return title_cards

    def start_task(self, card):
        """点击任务卡片开始任务"""
        action = ActionChains(self.web_driver)
        action.move_to_element(card).perform()

        start_elem = card.find_element(By.CSS_SELECTOR, '.task-card-content .content-start')
        print(f"开始任务按钮文本: {start_elem.text}")

        # 检查是否跳转到新页面
        original_url = self.web_driver.current_url
        start_elem.click()
        time.sleep(3)
        new_url = self.web_driver.current_url
        is_jumped = original_url != new_url

        print(f"原URL: {original_url}, 新URL: {new_url}, 是否跳转: {is_jumped}")
        return self.handle_task_modal() and is_jumped