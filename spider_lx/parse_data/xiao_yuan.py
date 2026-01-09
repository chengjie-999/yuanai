import time

from selenium.common import NoSuchElementException, ElementNotInteractableException
from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from spider_lx.auto.web.selenium.highlight_elements import highlight_elements
from spider_lx.save_data.save_data import *


class XiaoYuan:

    def __init__(self, web_driver: WebDriver):
        self.web_driver = web_driver
        self.wait = WebDriverWait(web_driver, 30)  # （最长等10秒，每0.5秒轮询一次）每进行一次页面加载时执行一次显式等待
        self.action = ActionChains(web_driver)

    def get_html(self):
        html = self.web_driver.page_source
        print(html)
        sd = SavedData(f'小猿')
        sd.save_data_html(html)

    def start(self, card):
        """
        任务卡片点击开始任务
        :param card: 任务卡片
        :return:
        """
        action = ActionChains(self.web_driver)
        action.move_to_element(card).perform()
        start = card.find_element(by=By.CSS_SELECTOR, value='.task-card-content .content-start')
        print(start.text)
        start.click()  # 点击开始任务
        try:
            # 处理任务不足
            card_no = self.web_driver.find_element(by=By.CSS_SELECTOR, value='.ant-modal-confirm-btns')
            card_no.click()
        except NoSuchElementException:
            return True

        return False

    def home(self):
        """
        小猿众包主页
        :return:
        """
        # 执行主页操作，找到任务卡片
        cards = self.wait.until(
            EC.visibility_of_all_elements_located((By.CSS_SELECTOR, ".task-card"))  # 核心：条件 + 定位器 所有匹配元素存在且可见（返回元素列表）
        )
        # cards = web_driver.find_elements(By.CSS_SELECTOR, ".task-card")
        title_cards = {}
        for card in cards:
            # 各个任务卡片，通过标题寻找目标任务
            title = card.find_element(by=By.CSS_SELECTOR, value='.task-card-title').text
            # i = 0
            title = title.strip()
            # 任务状态 text-warning
            try:
                warn = card.find_element(By.CSS_SELECTOR, value='.text-warning:nth-child(2)').text
            except Exception as e:
                e.args = '暂无任务'
                break

            title = f'{title}【{warn}】'
            print(title)
            title_cards[title] = card

        # print(title_cards)
        return title_cards

    def go_question(self, name):
        """
        处理任务
        :param name: 任务名
        :return:
        """
        if '单题标答-审核' in name:
            # 题目 .ol-viewport
            question = self.wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, '.ol-viewport'))
            )
            # question = web_driver.find_element(By.CSS_SELECTOR, '.ol-viewport')

            # 找到独立答案 .yst-mathjax-loading
            try:
                # 尝试查找元素（这里用ID定位，实际替换为你的定位器）
                answer = question.find_element(By.CSS_SELECTOR, ".yst-mathjax-loading")
                # 如果找到元素，执行后续操作（如点击、输入）
                answer.click()
                time.sleep(0.5)
                # 点击正确按钮 ant-btn ant-btn-primary button_gjJ0I auditPassButton_OH_ef
                true = question.find_element(By.CSS_SELECTOR, '.button_gjJ0I')
                true.click()
                print('独立答案判断完成')
            except NoSuchElementException:
                # 找不到元素时执行的“跳过”逻辑（可根据需求修改）
                print("未找到【独立批改答案】，已跳过")
            except ElementNotInteractableException:
                print('【独立批改答案】交互隐藏！')

            # 找到第一个的黄框（批改答案） .ol-overlay-container 点击
            try:
                answer = question.find_element(By.CSS_SELECTOR, '.ol-overlay-container')
                # for answer in answers:
                answer.click()
                print('答案点击完成！')
                time.sleep(0.5)
                # 判断按钮，点击正确
                # 正确 .button_3sIPu  1
                # 错误 .button_3sIPu  2
                true = question.find_element(By.CSS_SELECTOR, '.button_3sIPu')
                # 全部正确
                answers = question.find_elements(By.CSS_SELECTOR, '.ol-overlay-container')
                for i in range(len(answers)):
                    true.click()
                print('答案判断完成！')
            except NoSuchElementException:
                # 找不到元素时执行的“跳过”逻辑（可根据需求修改）
                print("未找到【批改答案】，已跳过")
            except ElementNotInteractableException:
                print('【批改答案】交互隐藏！')
                # 滚动滑轮
                ActionChains(self.web_driver).send_keys(Keys.SPACE*5).perform()
                pass
            except Exception:
                pass
        elif '3.0改错-补答' in name:
            # .ant-radio-input 点击已完成补答修改

            # .ant-btn-primary 点击提交
            pass
        return

    def go_home(self):
        home = self.web_driver.find_element(By.CSS_SELECTOR, '.ant-menu-item')
        home.click()
        print('回首页')

    def compete(self, status):
        """
        提交任务
        :param status: 任务状态
        :return:
        """
        if not status:
            status = '提交领下一任务'
        foot = self.web_driver.find_element(By.CSS_SELECTOR, '.container_23Xxj')
        if status == '提交领下一任务':
            button = foot.find_elements(By.CSS_SELECTOR, '.ant-btn')[-1]
            print(button.text)
            button.click()
        elif status == '提交回首页':
            button = foot.find_element(By.CSS_SELECTOR, '.ant-btn')
            button.click()
        elif status == '整题驳回':
            button = foot.find_elements(By.CSS_SELECTOR, '.ant-btn')[1]
            button.click()
            # 驳回理由
        else:
            button = foot.find_element(By.CSS_SELECTOR,
                                       '.ant-space:nth-child(2) .ant-space-item:nth-child(5) .ant-btn')
            button.click()
        try:
            # 处理任务不足，点击后返回首页。
            card_no = self.web_driver.find_element(by=By.CSS_SELECTOR, value='.ant-modal-confirm-btns')
            card_no.click()
            self.go_home()
        except NoSuchElementException:
            print('任务充足')


if __name__ == '__main__':
    pass
