from langchain_core.tools import tool

from spiderlx.auto.web.selenium.main import MyWebBrowser
from spiderlx.ui.selenium.resource import get_driver

_browser_instance: MyWebBrowser | None = None


@tool
def launch_new_browser() -> str:
    """
    启动浏览器实例，是所有网页操作的前置条件。
    如果浏览器已启动，则直接返回成功；否则创建新实例。

    Returns:
        成功: "✅ 新浏览器窗口已启动" 或 "✅ 浏览器已启动"
        失败: "❌ 启动新浏览器失败：{错误详情}"
    """
    global _browser_instance
    if _browser_instance:
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
    获取当前配置的网站信息（如可用的网站列表及编号）。
    需先调用 launch_new_browser。

    Returns:
        成功: "✅ 网站信息：{网站详情}"
        失败: 提示未启动浏览器或获取失败
    """
    if not _browser_instance:
        return "❌ 请先调用 launch_new_browser 启动浏览器"
    try:
        info = _browser_instance.website_info
        return f"✅ 网站信息：{info}"
    except Exception as e:
        return f"❌ 获取网站信息失败：{str(e)}"


@tool
def open_website_by_code(code: int) -> str:
    """
    根据编号打开预设网站。编号从 0 开始，可通过 get_website_info 获取列表。
    需先调用 launch_new_browser。

    Args:
        code: 网站编号（整数，从0开始）

    Returns:
        成功: "✅ 已打开网站：{网站名称}"
        失败: 提示未启动浏览器或打开失败
    """
    if not _browser_instance:
        return "❌ 请先调用 launch_new_browser 启动浏览器"
    try:
        name = _browser_instance.open_website(code=code)
        return f"✅ 已打开网站：{name}"
    except Exception as e:
        return f"❌ 打开网站失败：{str(e)}"


@tool
def open_website_by_name(name: str) -> str:
    """
    根据名称打开预设网站。名称需与配置中的网站名一致。
    需先调用 launch_new_browser。

    Args:
        name: 网站名称（如："小猿众包"）

    Returns:
        成功: "✅ 已打开网站：{网站名称}"
        失败: 提示未启动浏览器或打开失败
    """
    if not _browser_instance:
        return "❌ 请先调用 launch_new_browser 启动浏览器"
    try:
        _browser_instance.open_website(name=name)
        return f"✅ 已打开网站：{name}"
    except Exception as e:
        return f"❌ 打开网站失败：{str(e)}"


@tool
def open_custom_url(url: str) -> str:
    """
    打开任意自定义网址（非预设网站）。
    需先调用 launch_new_browser。

    Args:
        url: 完整网址，如 "https://www.example.com"

    Returns:
        成功: "✅ 已打开网址：{url}"
        失败: 提示未启动浏览器或打开失败
    """
    if not _browser_instance:
        return "❌ 请先调用 launch_new_browser 启动浏览器"
    try:
        _browser_instance.open_website(url=url)
        return f"✅ 已打开网址：{url}"
    except Exception as e:
        return f"❌ 打开网址失败：{str(e)}"


@tool
def refresh_page() -> str:
    """
    刷新当前浏览器页面。
    需先调用 launch_new_browser 并已打开某个网页。

    Returns:
        成功: "✅ 页面已刷新"
        失败: 提示未启动浏览器或刷新失败
    """
    if not _browser_instance:
        return "❌ 请先调用 launch_new_browser 启动浏览器"
    try:
        _browser_instance.refresh()
        return "✅ 页面已刷新"
    except Exception as e:
        return f"❌ 刷新失败：{str(e)}"


@tool
def load_cookies() -> str:
    """
    加载本地保存的 Cookie 到当前浏览器页面。
    需先调用 launch_new_browser 并打开目标网站。

    Returns:
        成功: "✅ Cookie 已加载"
        失败: 提示未启动浏览器或加载失败或未找到 Cookie 文件
    """
    if not _browser_instance:
        return "❌ 请先调用 launch_new_browser 启动浏览器并打开网站"
    try:
        have = _browser_instance.use_cookies()
        if have:
            return "✅ Cookie 已加载"
        else:
            return '⚠️ 没有找到可用的 Cookie 文件，未加载成功，需提示用户手动登录！'
    except Exception as e:
        return f"❌ 加载 Cookie 失败：{str(e)}"


@tool
def save_cookies() -> str:
    """
    保存当前页面的 Cookie 到本地文件。
    需先调用 launch_new_browser 并已打开网页。

    Returns:
        成功: "✅ Cookie 已保存"
        失败: 提示未启动浏览器或保存失败
    """
    if not _browser_instance:
        return "❌ 请先调用 launch_new_browser 启动浏览器并打开网站"
    try:
        _browser_instance.get_cookies()
        return "✅ Cookie 已保存"
    except Exception as e:
        return f"❌ 保存 Cookie 失败：{str(e)}"


@tool
def close_browser() -> str:
    """
    关闭浏览器窗口（若为接管模式，仅断开连接，不关闭真实窗口）。
    需先调用 launch_new_browser。

    Returns:
        成功: "✅ 浏览器已关闭"
        失败: 提示未启动浏览器或关闭失败
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