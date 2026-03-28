from langchain_core.tools import tool

from spiderlx.auto.web.selenium.main import MyWebBrowser
from spiderlx.ui.selenium.resource import get_driver

_browser_instance: MyWebBrowser | None = None


@tool
def launch_new_browser() -> str:
    """
    启动一个新的浏览器窗口
    """
    global _browser_instance
    if _browser_instance:
        print(_browser_instance)
        return "✅ 浏览器已启动"
    try:
        _browser_instance = get_driver()
        return "✅ 新浏览器窗口已启动"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ 启动新浏览器失败：{str(e)}"


@tool
def get_website_info() -> str:
    """
    获取网站信息
    """
    if not _browser_instance:
        return "❌ 请先调用 launch_new_browser"

    try:
        info = _browser_instance.website_info
        return f"✅ 网站信息：{info}"
    except Exception as e:
        return f"❌ 获取网站信息失败：{str(e)}"


# ----------------------
# 工具 3：打开网站（按编号）
# ----------------------
@tool
def open_website_by_code(code: int) -> str:
    """
    打开指定编号的网站
    参数 code：网站编号（从 0 开始）
    """
    if not _browser_instance:
        return "❌ 请先调用 launch_new_browser"

    try:
        name = _browser_instance.open_website(code=code)
        return f"✅ 已打开网站：{name}"
    except Exception as e:
        return f"❌ 打开网站失败：{str(e)}"


# ----------------------
# 工具 4：打开网站（按名称）
# ----------------------
@tool
def open_website_by_name(name: str) -> str:
    """
    打开指定名称的网站
    参数 name：网站名称（如：小猿众包）
    """
    if not _browser_instance:
        return "❌ 请先启动浏览器"

    try:
        _browser_instance.open_website(name=name)
        return f"✅ 已打开网站：{name}，如果该网站在get_website_info中可以查到，则执行load_cookies"
    except Exception as e:
        return f"❌ 打开网站失败：{str(e)}"


# ----------------------
# 工具 5：打开自定义网址
# ----------------------
@tool
def open_custom_url(url: str) -> str:
    """
    打开自定义网址
    参数 url：完整网址（如：https://www.example.com）
    """
    print(_browser_instance)
    if not _browser_instance:
        return "❌ 请先启动浏览器"

    try:
        _browser_instance.open_website(url=url)
        return f"✅ 已打开网址：{url}"
    except Exception as e:
        return f"❌ 打开网址失败：{str(e)}"


# ----------------------
# 工具 6：刷新页面
# ----------------------
@tool
def refresh_page() -> str:
    """
    刷新当前页面
    """
    if not _browser_instance:
        return "❌ 请先启动浏览器"

    try:
        _browser_instance.refresh()
        return "✅ 页面已刷新"
    except Exception as e:
        return f"❌ 刷新失败：{str(e)}"


# ----------------------
# 工具 7：加载并使用 Cookie
# ----------------------
@tool
def load_cookies() -> str:
    """
    加载并使用本地保存的 Cookie
    """
    if not _browser_instance:
        return "❌ 请先启动浏览器并打开网站"

    try:
        _browser_instance.use_cookies()
        return "✅ Cookie 已加载，请调用open_website_by_name重新访问该网站！"
    except Exception as e:
        return f"❌ 加载 Cookie 失败：{str(e)}"


# ----------------------
# 工具 8：保存当前 Cookie
# ----------------------
@tool
def save_cookies() -> str:
    """
    保存当前页面的 Cookie 到本地
    """
    if not _browser_instance:
        return "❌ 请先启动浏览器并打开网站"

    try:
        _browser_instance.get_cookies()
        return "✅ Cookie 已保存"
    except Exception as e:
        return f"❌ 保存 Cookie 失败：{str(e)}"


# ----------------------
# 工具 9：关闭浏览器
# ----------------------
@tool
def close_browser() -> str:
    """
    关闭浏览器（接管模式仅断开连接，不关闭真实窗口）
    """
    global _browser_instance
    if not _browser_instance:
        return "❌ 浏览器未启动"

    try:
        _browser_instance.close_browser()
        _browser_instance = None
        return "✅ 浏览器已关闭"
    except Exception as e:
        return f"❌ 关闭浏览器失败：{str(e)}"
