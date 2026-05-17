import random
import threading
import time
from typing import Optional

from langchain_core.tools import tool

from spiderlx.auto.web.selenium.xiaoyuan.xiaoyuan import SeleniumXiaoYuan, SingleAuditHandler
from spiderlx.core.browser_manager import browser_manager
from yuanai.tools.errors import classify_error


_xiao_yuan: Optional[SeleniumXiaoYuan] = None
_sa: Optional[SingleAuditHandler] = None
_xy_lock = threading.Lock()
_sa_lock = threading.Lock()


def _get_browser_driver():
    """获取共享浏览器驱动，优先使用已启动的浏览器，必要时自动启动"""
    bw = browser_manager.get_driver()
    if bw:
        return bw.driver
    browser_manager.start()
    bw = browser_manager.get_driver()
    if bw:
        return bw.driver
    raise RuntimeError("浏览器启动失败")


def _get_xiao_yuan() -> SeleniumXiaoYuan:
    global _xiao_yuan
    if _xiao_yuan is not None:
        return _xiao_yuan
    with _xy_lock:
        if _xiao_yuan is not None:
            return _xiao_yuan
        driver = _get_browser_driver()
        current = driver.current_url
        if 'xyzb.yuanfudao.com' not in current:
            driver.get("https://xyzb.yuanfudao.com/")
            time.sleep(random.randint(2, 5))
            try:
                from spiderlx.anti.cookie.selenium import use_cookie, get_cookie
                if use_cookie(driver):
                    driver.refresh()
                    time.sleep(2)
                    get_cookie(driver)  # 自动续期已保存的 Cookie
            except Exception:
                pass
        _xiao_yuan = SeleniumXiaoYuan(driver)
    return _xiao_yuan


def _get_sa() -> SingleAuditHandler:
    global _sa
    if _sa is not None:
        return _sa
    with _sa_lock:
        if _sa is not None:
            return _sa
        _sa = SingleAuditHandler(_get_xiao_yuan())
    return _sa


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
    print(f"📋 get_task_cards: {len(titles)} 个任务, 目标={target}")
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
    print(f"▶️ start_task: card_index={card_index} → {'成功' if success else '失败'}")
    return f"开始任务{'成功' if success else '失败'}"


@tool
def go_home() -> str:
    """返回主页。"""
    _get_xiao_yuan().go_home()
    return "已返回主页"


@tool
def save_page_html() -> str:
    """保存当前页面 HTML 到本地。"""
    _get_xiao_yuan().get_html()
    return "当前页面 HTML 已保存"


@tool
def get_question_info() -> str:
    """
    获取当前题目的截图和参考答案信息。
    图片保存在本地 data/qimg/ 目录并返回 URL 路径。
    """
    import json, os, uuid
    from utils.data_path import root_path

    sa = _get_sa()
    xy = _get_xiao_yuan()
    qa = sa.question_info()
    current_url = xy.web_driver.current_url
    task_name = getattr(xy, '_current_task_name', '未知任务')

    img_id = str(uuid.uuid4())
    img_dir = os.path.join(root_path(), 'data', 'qimg', img_id)
    os.makedirs(img_dir, exist_ok=True)

    images_meta = []
    urls = []

    for i, item in enumerate(qa):
        ext = "png"
        file_name = f"{i}.{ext}"
        file_path = os.path.join(img_dir, file_name)

        if isinstance(item, bytes):
            with open(file_path, 'wb') as f:
                f.write(item)
            images_meta.append({"index": i, "type": "screenshot" if i == 0 else "reference" if i == 1 else "mark"})
            urls.append(f"/api/v1/browser/qimg/{img_id}/{file_name}")
        elif isinstance(item, str):
            if item.startswith("data:image"):
                import base64
                b64_data = item.split(",", 1)[-1]
                with open(file_path, 'wb') as f:
                    f.write(base64.b64decode(b64_data))
                images_meta.append({"index": i, "type": "screenshot" if i == 0 else "reference" if i == 1 else "mark"})
                urls.append(f"/api/v1/browser/qimg/{img_id}/{file_name}")
            else:
                # 只保留 HTTP URL（参考答案），跳过本地文件路径（如独立.png）
                if item.startswith('http'):
                    urls.append(item)
                    images_meta.append({"index": i, "type": "url", "url": item})

    # 写 meta.json
    meta = {
        "id": img_id,
        "url": current_url,
        "task_name": task_name,
        "create_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "images": images_meta,
    }
    with open(os.path.join(img_dir, 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 存数据库
    try:
        from db.session import get_db
        db = get_db()
        db.save_task_images(img_id, task_name, current_url, img_dir, len(urls), images_meta)
    except Exception as e:
        print(f"⚠️ 保存图片记录到数据库失败: {e}")

    return json.dumps({"count": len(urls), "images": [{"type": "url", "data": u} for u in urls]}, ensure_ascii=False)


@tool
def submit_task(action: str = "提交领下一任务", reject_reason: str = "") -> str:
    """
    提交当前任务或驳回。
    参数 action: '提交领下一任务'（默认）、'整题驳回'
    参数 reject_reason: 驳回原因（action 为 '整题驳回' 时必填）
    返回是否可继续。
    """
    if action == "整题驳回" and not reject_reason:
        return "错误：整题驳回必须提供 reject_reason 参数"
    can_continue = _get_sa().compete(action, cause=reject_reason)
    print(f"📤 submit_task: action={action} → {'可以继续' if can_continue else '终止'}")
    return f"操作完成，{'可以继续任务' if can_continue else '任务终止或需手动处理'}"


@tool
def zoom_question(count: int = 6) -> str:
    """
    缩小题目视图（默认6次点击）。
    参数 count: 点击缩小次数（默认6）
    """
    _get_sa().question_resize(count=count)
    return f"已缩小题目视图 {count} 次"


@tool
def restore_question_view() -> str:
    """恢复题目视图到原始大小。"""
    success = _get_sa().question_restore()
    return "已恢复题目视图" if success else "恢复失败"


@tool
def mark_question_correct() -> str:
    """
    标记当前题目审核正确。
    处理独立答案和批改答案的判定操作。
    """
    _get_sa().quick_true_handle(up=False)
    return "已标记审核正确"


@tool
def confirm_rejection() -> str:
    """
    确认驳回弹窗。
    在调用 submit_task(action='整题驳回') 之后调用，确认驳回操作。
    """
    text = _get_sa().rejection_confirmation()
    return f"驳回已确认：{text}"


@tool
def scroll_canvas(direction: str = "down", amount: int = 1000) -> str:
    """
    滚动画布中的题目内容（优先 Selenium ActionChains，支持无头模式）。
    题目在画布中可能显示不全，需要滚动才能查看到完整内容。
    在审核前建议先滚动查看完整题目，再调用 get_question_info 获取截图分析。
    参数 direction: 'down' 向下滚动（显示下方内容）/ 'up' 向上滚动（显示上方内容）
    参数 amount: 滚动量（默认1000，数值越大滚得越多）
    """
    from spiderlx.auto.canvas.core import scroll
    driver = _get_xiao_yuan().web_driver
    success = scroll(direction=direction, amount=amount, driver=driver)
    return f"已向{'下' if direction=='down' else '上'}滚动" if success else "滚动失败"


@tool
def click_canvas(x: int, y: int) -> str:
    """
    点击画布指定坐标（优先 Selenium ActionChains，支持无头模式）。
    用于点击画布中特定位置，选中某个黄框进行操作。
    参数 x: 屏幕 x 坐标（画布中心约 1000）
    参数 y: 屏幕 y 坐标（画布中心约 600）
    """
    from spiderlx.auto.canvas.core import click
    driver = _get_xiao_yuan().web_driver
    success = click(x, y, driver=driver)
    return f"已点击坐标 ({x}, {y})" if success else f"点击失败"


@tool
def load_page_cookies() -> str:
    """
    加载小猿众包保存的 Cookie 到当前浏览器，用于自动登录。
    需先打开小猿众包网站。
    如有手动输入验证码等需要，会提示用户。
    """
    try:
        from spiderlx.anti.cookie.selenium import use_cookie, get_cookie
        driver = _get_xiao_yuan().web_driver
        have = use_cookie(driver)
        if have:
            driver.refresh()
            time.sleep(2)
            get_cookie(driver)  # 自动续期
            return "✅ Cookie 已加载，页面已刷新"
        return "⚠️ 未找到 Cookie 文件，请先手动登录后调用 save_page_cookies"
    except Exception as e:
        return classify_error(e, "加载 Cookie 失败")


@tool
def save_page_cookies() -> str:
    """
    保存当前小猿众包页面的 Cookie 到本地文件。
    在手动登录后调用，保存登录状态供后续自动使用。
    """
    try:
        from spiderlx.anti.cookie.selenium import get_cookie
        driver = _get_xiao_yuan().web_driver
        get_cookie(driver)
        return "✅ Cookie 已保存"
    except Exception as e:
        return classify_error(e, "保存 Cookie 失败")


@tool
def get_page_status() -> str:
    """
    获取当前页面状态（是否有弹窗、当前任务信息等）。
    在执行操作前调用，了解页面当前情况。
    """
    try:
        xy = _get_xiao_yuan()
        driver = xy.web_driver
        current_url = driver.current_url
        page_source = driver.page_source
        status_parts = [f"当前URL: {current_url}"]

        if 'xyzb.yuanfudao.com' not in current_url:
            status_parts.append("⚠️ 不在小猿众包网站")
            return '\n'.join(status_parts)

        if 'task' in current_url or 'question' in current_url:
            status_parts.append("📌 当前在任务页面")
        elif 'home' in current_url or current_url.endswith('.com/') or current_url.endswith('.com'):
            status_parts.append("🏠 当前在主页")

        from selenium.common import NoSuchElementException
        try:
            modal = driver.find_element('css selector', '.ant-modal-content')
            title = modal.find_element('css selector', '.ant-modal-confirm-title')
            status_parts.append(f"🔔 弹窗提示: {title.text}")
            btns = modal.find_elements('css selector', '.ant-btn')
            btn_texts = [b.text.strip() for b in btns if b.text.strip()]
            if btn_texts:
                status_parts.append(f"  按钮: {', '.join(btn_texts)}")
        except NoSuchElementException:
            status_parts.append("✅ 无弹窗")

        try:
            btn_primary = driver.find_elements('css selector', '.ant-btn-primary')
            if btn_primary:
                texts = [b.text.strip() for b in btn_primary if b.text.strip()]
                if texts:
                    status_parts.append(f"🔄 可操作按钮: {', '.join(texts[:3])}")
        except NoSuchElementException:
            pass

        return '\n'.join(status_parts)
    except Exception as e:
        return classify_error(e, "获取页面状态失败")