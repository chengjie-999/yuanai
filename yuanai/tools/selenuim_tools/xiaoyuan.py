import atexit
import random
import time
from typing import Optional
from langchain_core.tools import tool

# 全局单例
from spiderlx.auto.web.selenium.main import MyWebBrowser, BrowserInitializer
from spiderlx.auto.web.selenium.xiaoyuan.xiaoyuan import SeleniumXiaoYuan
from yuanai.tools.selenuim_tools.core import browser_instance

_driver: Optional[MyWebBrowser] = browser_instance
xiao_yuan: Optional[SeleniumXiaoYuan] = None


def _get_xiao_yuan() -> SeleniumXiaoYuan:
    global _driver, xiao_yuan
    if _driver is None:
        _driver = MyWebBrowser(BrowserInitializer().create_driver())
        atexit.register(lambda: _driver.close_browser())
    if xiao_yuan is None:
        # 使用 code 或明确 name，确保配置存在
        _driver.open_website(name='小猿众包')  # 或 code=0
        # 加载 Cookie，如果失败可尝试手动登录
        if not _driver.use_cookies():
            print("⚠️ Cookie 加载失败，请手动登录后调用 get_cookies 保存")
        xiao_yuan = SeleniumXiaoYuan(_driver.driver)
        time.sleep(random.randint(2, 5))
    return xiao_yuan


@tool
def get_task_cards(keyword: str = "单题标答-审核") -> str:
    """
    获取主页任务卡片列表，按关键词筛选。
    参数 keyword: 任务名称关键词（默认"单题标答-审核"）
    返回所有任务标题及匹配到的第一个目标标题。
    """
    xy = _get_xiao_yuan()
    title_cards = xy.home_card(like=keyword)
    titles = list(title_cards.keys())
    target = titles[0] if titles else None
    return f"共获取 {len(titles)} 个任务卡片。\n所有标题：{titles}\n匹配到的目标：{target}"


@tool
def start_task(card_title: str = None, card_index: int = 0) -> str:
    """
    开始一个任务。可通过卡片标题（完整字符串）或索引指定卡片。
    参数 card_title: 任务卡片完整标题（如 '单题标答-审核【暂无任务】'）
    参数 card_index: 卡片索引（默认0），当 card_title 未提供时使用。
    返回是否成功进入任务。
    """
    xy = _get_xiao_yuan()
    # 获取所有卡片
    title_cards = xy.home_card()
    if card_title:
        card = title_cards.get(card_title)
        if not card:
            return f"未找到标题为 '{card_title}' 的卡片，请检查。"
    else:
        cards = list(title_cards.values())
        if card_index >= len(cards):
            return f"索引 {card_index} 超出范围，共有 {len(cards)} 个卡片。"
        card = cards[card_index]
    success = xy.start(card)
    return f"开始任务{'成功' if success else '失败'}（可能被弹窗阻断）"


@tool
def handle_current_question(task_name: str, audit_result: str = "1", zoom: bool = False) -> str:
    """
    处理当前题目（审核/补答等）。
    参数 task_name: 任务名称，如 '单题标答-审核'、'3.0改错-补答'、'抄写图形题-补答审核'
    参数 audit_result: 审核结果，'1' 通过，'0' 不通过（仅对抄写图形题有效）
    参数 zoom: 是否先缩小题目视图（默认 False）
    """
    xy = _get_xiao_yuan()
    xy.go_question(name=task_name, true=audit_result, up=zoom)
    return f"已完成题目处理（任务类型：{task_name}）"


@tool
def submit_or_reject(action: str, reject_reason: str = "") -> str:
    """
    提交任务或整题驳回。
    参数 action: 可选值 '提交领下一任务'、'提交回首页'、'整题驳回'
    参数 reject_reason: 驳回原因（当 action 为 '整题驳回' 时必填）
    返回是否可继续任务。
    """
    xy = _get_xiao_yuan()
    if action == "整题驳回" and not reject_reason:
        return "错误：整题驳回必须提供 reject_reason 参数"
    can_continue = xy.compete(status=action, cause=reject_reason)
    return f"操作完成，{'可以继续任务' if can_continue else '任务终止或需手动处理'}"


@tool
def go_home() -> str:
    """返回主页。"""
    xy = _get_xiao_yuan()
    xy.go_home()
    return "已返回主页"


@tool
def get_question_info(take_screenshots: bool = True) -> str:
    """
    获取当前题目的全局截图、参考答案图片链接及截图路径。
    参数 take_screenshots: 是否截取独立答案和标记答案图片（默认 True）
    返回简要信息。
    """
    xy = _get_xiao_yuan()
    info = xy.question_info(screenshot=take_screenshots)
    # info 结构：[全局截图bytes, 参考答案src, 独立答案路径?, 标记答案路径1, ...]
    full_screenshot_size = len(info[0]) if isinstance(info[0], bytes) else 0
    refer_src = info[1] if len(info) > 1 else "无"
    other_paths = info[2:] if len(info) > 2 else []
    return (f"全局截图大小 {full_screenshot_size} 字节，参考答案图片 {refer_src}，"
            f"额外截图/路径 {len(other_paths)} 个")


@tool
def zoom_question(times: int = 6, restore: bool = False) -> str:
    """
    缩放题目视图（缩小）或恢复原始大小。
    参数 times: 点击缩小次数（默认6，仅当 restore=False 时生效）
    参数 restore: 是否恢复视图（默认 False）
    """
    xy = _get_xiao_yuan()
    if restore:
        xy.question_restore()
        return "已恢复题目视图"
    else:
        xy.question_resize(count=times)
        return f"已缩小题目视图 {times} 次"


@tool
def save_page_html() -> str:
    """保存当前页面 HTML 到本地。"""
    xy = _get_xiao_yuan()
    xy.get_html()
    return "当前页面 HTML 已保存"
