import time

from selenium.common import (
    NoSuchElementException,
    ElementNotInteractableException,
    WebDriverException
)
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from spiderlx.core.save.save_data import SavedData
from utils.data_path import img_save_path

import pyautogui
import time
from spiderlx.auto.canvas.core import scroll as canvas_scroll


class SeleniumXiaoYuan:
    """
    小猿众包自动化业务类
    功能：任务处理、题目操作、答案审核、截图保存、弹窗处理、任务导航
    """

    def __init__(self, web_driver: WebDriver):
        self.web_driver = web_driver
        self.wait = WebDriverWait(self.web_driver, 30)

    def get_html(self):
        """获取页面HTML并保存"""
        html = self.web_driver.page_source
        print(html)
        save = SavedData('小猿')
        save.save_data_html(html)

    def start(self, card):
        """
        点击任务卡片开始任务
        :param card: 任务卡片元素
        :return: 是否成功进入任务
        """
        ActionChains(self.web_driver).move_to_element(card).perform()
        start_btn = card.find_element(By.CSS_SELECTOR, '.task-card-content .content-start')
        print(f"开始任务按钮文本：{start_btn.text}")

        current_url = self.web_driver.current_url
        start_btn.click()
        time.sleep(3)
        new_url = self.web_driver.current_url

        go_on = current_url != new_url
        print(f"原URL：{current_url} | 新URL：{new_url} | 是否跳转：{go_on}")
        return self.box() and go_on

    def home_card(self, like='单题标答-审核'):
        """
        主页加载任务卡片，筛选目标任务
        :param like: 偏好任务名称关键词
        :return: 任务标题与卡片映射字典
        """
        cards = self.wait.until(
            EC.visibility_of_all_elements_located((By.CSS_SELECTOR, ".task-card"))
        )
        title_cards = {}

        for card in cards:
            title = "未知任务"
            try:
                title = card.find_element(By.CSS_SELECTOR, '.task-card-title').text.strip()
            except Exception as e:
                pass
            try:
                warn_text = card.find_element(By.CSS_SELECTOR, '.text-warning:nth-child(2)').text
            except:
                warn_text = '暂无任务'

            full_title = f'{title}【{warn_text}】'
            title_cards[full_title] = card
            print(full_title)

            if like in full_title:
                break
        return title_cards

    def handle_fix_answer(self):
        """3.0改错-补答 逻辑（可扩展）"""
        pass

    def handle_copy_audit(self, true):
        """抄写图形题-补答审核 逻辑"""
        radios = self.web_driver.find_elements(By.CSS_SELECTOR, '.ant-radio-input')
        submit = self.web_driver.find_elements(By.CSS_SELECTOR, '.ant-btn-primary')[-1]

        if true:
            radios[0].click()
            submit.click()
        else:
            radios[1].click()

    def go_home(self):
        """返回主页"""
        self.web_driver.find_element(By.CSS_SELECTOR, '.ant-menu-item').click()
        print("返回首页")
        return True

    def box(self, go_on=True):
        """
        统一处理任务弹窗（任务不足/任务完成）
        :return: 是否继续任务
        """
        try:
            time.sleep(1.5)
            from selenium.common import TimeoutException, StaleElementReferenceException
            modal = WebDriverWait(self.web_driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.ant-modal-content'))
            )
            msg = modal.find_element(By.CSS_SELECTOR, '.ant-modal-confirm-title').text
            print(f"系统提示：{msg}")

            btns = self.web_driver.find_element(By.CSS_SELECTOR, '.ant-modal-confirm-btns')
            if '是否继续认领下一包' in msg and go_on:
                primary = btns.find_element(By.CSS_SELECTOR, '.ant-btn-primary')
                primary.click()
                return True
            else:
                btn = btns.find_element(By.CSS_SELECTOR, '.ant-btn')
                btn.click()
                return False
        except (NoSuchElementException, TimeoutException, StaleElementReferenceException):
            print("任务充足或无弹窗")
        return go_on

    def to_detail(self):
        """进入详情页"""
        self.web_driver.find_element(By.CSS_SELECTOR, '.content_2t03S a').click()

    def close_detail(self):
        """关闭详情页并保存"""
        handles = self.web_driver.window_handles
        if len(handles) > 1:
            self.web_driver.switch_to.window(handles[1])
            self.web_driver.find_element(By.CSS_SELECTOR, '.footer_3Vgpz .ant-space-item button').click()
            self.web_driver.close()
            self.web_driver.switch_to.window(handles[0])

    def safe_click(self, element):
        """万能安全点击：解决遮挡、不可点击问题"""
        try:
            element.click()
        except Exception:
            self.web_driver.execute_script("arguments[0].click();", element)


def scroll(center_x=1000, center_y=600, scroll_num=-1000):
    """向下滚动画布（委托 canvas.core.scroll）"""
    direction = "down" if scroll_num < 0 else "up"
    return canvas_scroll(direction=direction, amount=abs(scroll_num), x=center_x, y=center_y)


class SingleAuditHandler:
    """
    单题标答-审核 专用处理器
    包含该任务类型的特有交互：独立答案/批改答案点击、视图缩放/恢复、提交/驳回等
    """

    def __init__(self, xiao_yuan: SeleniumXiaoYuan):
        """
        :param xiao_yuan: 已经初始化的 SeleniumXiaoYuan 实例（组合复用）
        """
        self.xiao_yuan = xiao_yuan
        self.driver = xiao_yuan.web_driver
        self.wait = xiao_yuan.wait

    def quick_true_handle(self, up=True):
        """
        单题标答-审核 没有错误，直接点击【独立批改答案】和【批改答案】进行判断
        :param up: 是否需要先缩小视图，结束后恢复视图
        """
        question = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.ol-viewport')))

        if up:
            self.question_resize()
            time.sleep(1)

        # 处理独立答案
        try:
            answer = question.find_element(By.CSS_SELECTOR, ".yst-mathjax-loading")
            ActionChains(self.driver).move_to_element(answer).click().perform()
            time.sleep(0.5)
            question.find_element(By.CSS_SELECTOR, '.button_gjJ0I').click()
            print("独立答案判断完成")
        except NoSuchElementException:
            print("未找到【独立批改答案】，已跳过")
        except ElementNotInteractableException:
            print("【独立批改答案】不可交互")

        # 处理批改答案
        try:
            ActionChains(self.driver).move_to_element(question).perform()
            answer = question.find_element(By.CSS_SELECTOR, '.ol-overlay-container')
            answer.click()
            time.sleep(0.5)

            true_btn = question.find_element(By.CSS_SELECTOR, '.button_3sIPu')
            answers = question.find_elements(By.CSS_SELECTOR, '.ol-overlay-container')
            for _ in answers:
                true_btn.click()
            print("答案判断完成")
        except NoSuchElementException:
            print("未找到【批改答案】，已跳过")
        except ElementNotInteractableException:
            print("【批改答案】不可交互")
        except Exception:
            pass

        if up:
            self.question_restore()

    def compete(self, status, cause=None):
        """
        提交任务/驳回任务
        :param status: 提交状态
        :param cause: 驳回原因
        :return: 是否继续任务
        """
        foot = self.driver.find_element(By.CSS_SELECTOR, '.container_23Xxj')

        if status == '提交领下一任务':
            btn = foot.find_elements(By.CSS_SELECTOR, '.ant-btn')[-1]
        elif status == '提交回首页':
            btn = foot.find_element(By.CSS_SELECTOR, '.ant-btn')
        elif status == '整题驳回':
            btn = foot.find_elements(By.CSS_SELECTOR, '.ant-btn')[1]

            # 安全点击打开驳回弹窗
            self.xiao_yuan.safe_click(btn)
            time.sleep(2)
            try:
                input_box = self.wait.until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, '.ant-input'))
                )
                input_box.clear()
                input_box.send_keys(cause)
            except NoSuchElementException:
                print("⚠️ 未找到驳回输入框")

            # 找到确认按钮并安全点击
            confirm_btn = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '.ant-btn-primary'))
            )
            time.sleep(0.5)
            return self.xiao_yuan.box()
        else:
            btn = foot.find_element(By.CSS_SELECTOR, '.ant-space:nth-child(2) .ant-space-item:nth-child(5) .ant-btn')

        self.xiao_yuan.safe_click(btn)
        time.sleep(2)
        return self.xiao_yuan.box()

    def question_resize(self, count=6):
        """缩小题目视图"""
        zoom_out = self.driver.find_elements(By.CSS_SELECTOR, '.ol-zoom-out')[0]
        for _ in range(count):
            zoom_out.click()
            time.sleep(0.05)

    def question_restore(self):
        """恢复题目视图"""
        try:
            self.driver.find_elements(By.CSS_SELECTOR, '.ol-control')[3].click()
            return True
        except NoSuchElementException:
            return False

    def rejection_confirmation(self):
        """确认驳回弹窗"""
        modal = self.driver.find_element(By.CSS_SELECTOR, '.ant-modal-content')
        confirm = modal.find_element(By.CSS_SELECTOR, '.ant-btn-primary')
        print(f"确认驳回：{confirm.text}")
        confirm.click()
        return confirm.text

    def question_info(self, screenshot=True):
        """
        获取题目截图、参考答案、独立答案截图。
        :return: [全局截图 bytes, 参考答案 url, 独立答案截图路径]
        """
        qa = [self.driver.get_screenshot_as_png()]
        refer_img = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.ant-image > img')))
        qa.append(refer_img.get_attribute('src'))

        question = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.ol-viewport')))

        # 独立答案截图
        try:
            local = img_save_path('独立.png')
            question.find_element(By.CSS_SELECTOR, ".yst-mathjax-loading").screenshot(local)
            qa.append(local)
        except NoSuchElementException:
            qa.append(img_save_path('独立.png'))

        return qa


if __name__ == '__main__':
    pass
