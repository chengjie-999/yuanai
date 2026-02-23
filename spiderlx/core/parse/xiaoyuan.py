import base64
import time

from selenium.common import NoSuchElementException, ElementNotInteractableException, WebDriverException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from spiderlx.core.save.save_data import *
from utils.data_path import img_save_path


class SeleniumXiaoYuan:

    def __init__(self, web_driver: WebDriver):
        self.web_driver = web_driver

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
        url = self.web_driver.current_url
        start.click()  # 点击开始任务
        time.sleep(3)
        new_url = self.web_driver.current_url
        go_on = False if url == new_url else True
        print(url, new_url, go_on)
        return self.box() and go_on

    def home(self, like='单题标答-审核'):
        """
        小猿众包主页
        :return:
        """
        # 执行主页操作，找到任务卡片
        wait = WebDriverWait(self.web_driver, 30)  # （最长等10秒，每0.5秒轮询一次）每进行一次页面加载时执行一次显式等待
        cards = wait.until(
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
                warn = '暂无任务'

            title = f'{title}【{warn}】'
            print(title)
            title_cards[title] = card

            # 出现单题标答-审核就不选其他任务
            if like in title:
                break
        return title_cards

    def go_question(self, name, true='1', up=False):
        """
        处理任务
        :param true:
        :param up:
        :param name: 任务名
        :return: 图片列表
        """
        wait = WebDriverWait(self.web_driver, 30)  # （最长等10秒，每0.5秒轮询一次）每进行一次页面加载时执行一次显式等待
        if '单题标答-审核' in name:
            # 题目 .ol-viewport
            question = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, '.ol-viewport'))
            )
            # question = web_driver.find_element(By.CSS_SELECTOR, '.ol-viewport')
            if up:
                self.question_resize()
                time.sleep(1)

            # 找到独立答案 .yst-mathjax-loading
            try:
                # 尝试查找元素（这里用ID定位，实际替换为你的定位器）
                answer = question.find_element(By.CSS_SELECTOR, ".yst-mathjax-loading")
                ActionChains(self.web_driver).move_to_element(answer).perform()
                # 如果找到元素，执行后续操作（如点击、输入）
                answer.click()
                print(answer.text)
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

            # 找到第一个的初次审核的黄框（批改答案） .ol-overlay-container 点击
            try:
                ActionChains(self.web_driver).move_to_element(to_element=question).perform()

                answer = question.find_element(By.CSS_SELECTOR, '.ol-overlay-container')
                print(answer.text, __name__)
                ActionChains(self.web_driver).move_to_element(answer).perform()
                # 再点击
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
                return

            except NoSuchElementException:
                # 找不到元素时执行的“跳过”逻辑（可根据需求修改）
                print("未找到【批改答案】，已跳过")
            except ElementNotInteractableException:
                print(f'【批改答案】交互隐藏！{ElementNotInteractableException().msg}')
                # ActionChains(self.web_driver).send_keys(Keys.SPACE).perform()
            except Exception as e:
                # print('未知错误', e)
                pass

            if up:
                self.question_restore()
        if '3.0改错-补答' in name:
            # .ant-radio-input 点击已完成补答修改

            # .ant-btn-primary 点击提交
            pass
        if '抄写图形题-补答审核' in name:
            if true:
                # .ant-radio-input 点击已完成补答修改
                t = self.web_driver.find_elements(By.CSS_SELECTOR, '.ant-radio-input')[0]
                t.click()
                # .ant-btn-primary 点击提交
                t = self.web_driver.find_elements(By.CSS_SELECTOR, '.ant-btn-primary')[-1]
                t.click()
            if not true:
                # .ant-radio-input 点击已完成补答修改
                t = self.web_driver.find_elements(By.CSS_SELECTOR, '.ant-radio-input')[1]
                t.click()
                # .ant-btn-primary 点击提交
                t = self.web_driver.find_elements(By.CSS_SELECTOR, '.ant-btn-primary')[-1]
                # t.click()
            pass
        return

    def go_home(self):
        home = self.web_driver.find_element(By.CSS_SELECTOR, '.ant-menu-item')

        home.click()
        print('回首页')
        return True

    def compete(self, status, cause=None):
        """
        提交任务
        :param cause:
        :param status: 任务状态
        :return:是否继续
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
            # 填写理由
            ant_input = self.web_driver.find_element(By.CSS_SELECTOR, '.ant-input')
            ant_input.send_keys(cause)
        else:
            button = foot.find_element(By.CSS_SELECTOR,
                                       '.ant-space:nth-child(2) .ant-space-item:nth-child(5) .ant-btn')
            button.click()
        time.sleep(0.5)
        return self.box()

    def question_resize(self, down=True, count=6):
        """
        题目放大或缩小
        :param down:缩小
        :param count:点击缩小按钮的次数
        :return:
        """
        if down:
            # 减小按钮
            down_button = self.web_driver.find_elements(By.CSS_SELECTOR, '.ol-zoom-out')[0]
            for _ in range(count):
                down_button.click()
                time.sleep(0.05)
        else:
            pass

    def question_restore(self):
        """
        题目恢复到正常大小
        :return:
        """
        try:
            re = self.web_driver.find_elements(By.CSS_SELECTOR, '.ol-control')[3]
            re.click()
        except NoSuchElementException:
            return False
        return True

    def rejection_confirmation(self):
        """
        驳回确认
        :return:
        """
        # ant-modal-content
        reject = self.web_driver.find_element(By.CSS_SELECTOR, '.ant-modal-content')
        confirm = reject.find_element(By.CSS_SELECTOR, '.ant-btn-primary')
        print(confirm.text)
        confirm.click()
        return confirm.text

    def box(self, go_on=True):
        """
        任务消息提示框
        :return:是否继续
        """
        try:
            time.sleep(1)
            # 处理任务不足，点击后返回首页。
            # ant - modal - content
            box = self.web_driver.find_element(By.CSS_SELECTOR, '.ant-modal-content')
            # ant-modal-confirm-title
            message = box.find_element(By.CSS_SELECTOR, '.ant-modal-confirm-title').text
            print(message)
            if message == '当前任务包已处理完毕，是否继续认领下一包？' and go_on:
                know = self.web_driver.find_element(by=By.CSS_SELECTOR, value='.ant-modal-confirm-btns')
                get = know.find_element(By.CSS_SELECTOR, '.ant-btn-primary')
                get_ = get.text
                print(get_)
                get.click()
                return go_on
            # 点击知道了
            know = self.web_driver.find_element(by=By.CSS_SELECTOR, value='.ant-modal-confirm-btns')
            get = know.text
            print(get)
            know.click()
            if get == '知道了':
                return not go_on
        except NoSuchElementException:
            print('任务充足')
        return go_on

    def to_detail(self):
        """
        【抄写】进入题目详情页面
        :return:
        """
        detail = self.web_driver.find_element(By.CSS_SELECTOR, '.content_2t03S a')
        detail.click()
        pass

    def close_detail(self):
        """
        【抄写】关闭题目详情页面
        :return:
        """
        windows = self.web_driver.window_handles
        print(windows)
        if len(windows) > 1:
            self.web_driver.switch_to.window(windows[1])
            # 保存
            save = self.web_driver.find_element(By.CSS_SELECTOR, '.footer_3Vgpz .ant-space-item button')
            print(save.text)
            save.click()
            pass
            self.web_driver.close()
        self.web_driver.switch_to.window(windows[0])
        pass

    def question_info(self, screenshot=True):
        """
        题目的标记答案和参考答案
        :return:
        """
        qa = []
        wait = WebDriverWait(self.web_driver, 30)
        # 参考答案
        refer = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, '.ant-image > img'))
        )
        refer_img = refer.get_attribute('src')
        qa.append(refer_img)

        # 题目 .ol-viewport
        if screenshot:
            wait = WebDriverWait(self.web_driver, 30)
            question = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, '.ol-viewport'))
            )
            # question = web_driver.find_element(By.CSS_SELECTOR, '.ol-viewport')
            # 独立标记答案
            local = img_save_path('独立.png')
            try:
                answer = question.find_element(By.CSS_SELECTOR, ".yst-mathjax-loading")
                answer.screenshot(local)
                qa.append(local)
            except NoSuchElementException:
                qa.append(local)

            # 标记答案
            answers = question.find_elements(By.CSS_SELECTOR, '.ol-overlay-container')
            # answers = question.find_elements(By.CSS_SELECTOR, '.ol-overlaycontainer')
            print(len(answers))
            i = 0
            for answer in answers:
                try:
                    local = img_save_path(f'答案{i}.png')
                    mark = answer.screenshot(local)
                except WebDriverException:
                    # 元素无法截图
                    continue
                qa.append(local)
                i += 1
        # # 3. 定位 canvas 元素（先确保元素存在）
        # canvas_elem =question.find_element(By.TAG_NAME, "canvas")
        # print(canvas_elem)
        # print('*'*100)
        # # 4. 核心操作：注入 JavaScript 调用 toDataURL() 获取 Base64 内容
        # # 注意：JavaScript 中通过 arguments[0] 接收传入的 canvas 元素
        # canvas_base64 = self.web_driver.execute_script("""
        #    // 传入的 canvas 元素
        #    const canvas = arguments[0];
        #    // 调用 toDataURL() 返回 Base64 字符串
        #    return canvas.toDataURL("image/png");
        # """, canvas_elem)
        # if canvas_base64:
        #     # 5.1 去除 Base64 字符串头部的 "data:image/png;base64," 前缀
        #     base64_data = canvas_base64.split(",")[1]
        #
        #     # 5.2 解码 Base64 数据为二进制流
        #     image_binary = base64.b64decode(base64_data)
        #     print(image_binary)
        #     qa.append(image_binary)

        return qa


if __name__ == '__main__':
    pass
