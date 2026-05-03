from langchain_core.tools import tool
from spiderlx.core.browser_manager import browser_manager


@tool
def launch_new_browser() -> str:
    """
    启动浏览器实例，是所有网页操作的前置条件。
    如果浏览器已启动，则直接返回成功；否则创建新实例。
    """
    return browser_manager.start()


@tool
def get_website_info() -> str:
    """获取当前配置的网站信息（如可用的网站列表及编号）"""
    driver = browser_manager.get_driver()
    if not driver:
        return "❌ 请先调用 launch_new_browser 启动浏览器"
    try:
        info = driver.website_info
        return f"✅ 网站信息：{info}"
    except Exception as e:
        return f"❌ 获取网站信息失败：{str(e)}"


@tool
def open_website_by_code(code: int) -> str:
    """根据编号打开预设网站"""
    driver = browser_manager.get_driver()
    if not driver:
        return "❌ 请先调用 launch_new_browser 启动浏览器"
    try:
        name, target_url = driver.open_website(code=code)
        return f"✅ 已打开网站：{name} | {target_url}"
    except Exception as e:
        return f"❌ 打开网站失败：{str(e)}"


@tool
def open_website_by_name(name: str) -> str:
    """根据名称打开预设网站"""
    driver = browser_manager.get_driver()
    if not driver:
        return "❌ 请先调用 launch_new_browser 启动浏览器"
    try:
        name, target_url = driver.open_website(name=name)
        return f"✅ 已打开网站：{name} | {target_url}"
    except Exception as e:
        return f"❌ 打开网站失败：{str(e)}"


@tool
def open_custom_url(url: str) -> str:
    """打开任意自定义网址"""
    driver = browser_manager.get_driver()
    if not driver:
        return "❌ 请先调用 launch_new_browser 启动浏览器"
    try:
        name, target_url = driver.open_website(url=url)
        return f"✅ 已打开网址：{name} | {target_url}"
    except Exception as e:
        return f"❌ 打开网址失败：{str(e)}"


@tool
def refresh_page() -> str:
    """刷新当前浏览器页面"""
    driver = browser_manager.get_driver()
    if not driver:
        return "❌ 请先调用 launch_new_browser 启动浏览器并打开网页"
    try:
        driver.refresh()
        return "✅ 页面已刷新"
    except Exception as e:
        return f"❌ 刷新失败：{str(e)}"


@tool
def load_cookies() -> str:
    """加载本地保存的 Cookie 到当前浏览器页面"""
    driver = browser_manager.get_driver()
    if not driver:
        return "❌ 请先调用 launch_new_browser 启动浏览器并打开网站"
    try:
        have = driver.use_cookies()
        if have:
            return "✅ Cookie 已加载"
        return '⚠️ 没有找到可用的 Cookie 文件，未加载成功，需提示用户手动登录！'
    except Exception as e:
        return f"❌ 加载 Cookie 失败：{str(e)}"


@tool
def save_cookies() -> str:
    """保存当前页面的 Cookie 到本地文件"""
    driver = browser_manager.get_driver()
    if not driver:
        return "❌ 请先调用 launch_new_browser 启动浏览器并打开网站"
    try:
        driver.get_cookies()
        return "✅ Cookie 已保存"
    except Exception as e:
        return f"❌ 保存 Cookie 失败：{str(e)}"


@tool
def close_browser() -> str:
    """关闭浏览器窗口"""
    return browser_manager.stop()
