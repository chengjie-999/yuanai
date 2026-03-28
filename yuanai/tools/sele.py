from langchain_core.tools import tool

# ----------------------
# 【全局单例】AI 完全看不见，只给工具内部用
# ----------------------
from spiderlx.auto.web.selenium.main import get_browser

_browser_instance = None


# ----------------------
# 工具 1：接管浏览器（9222 端口）
# ----------------------
@tool
def open_managed_browser() -> str:
    """
    接管已手动打开的 Chrome 浏览器（9222 远程调试端口）。
    必须第一个调用！所有网页操作依赖此工具。
    无需重启浏览器，直接复用已打开的窗口。
    返回成功或失败提示。
    """
    global _browser_instance
    try:
        _browser_instance = get_browser()
        return "✅ 成功接管 9222 端口浏览器，可以开始操作"
    except Exception as e:
        return f"❌ 接管浏览器失败：{str(e)}"


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
        return "❌ 请先调用 open_managed_browser 或 launch_new_browser"

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
        return f"✅ 已打开网站：{name}"
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
        return "✅ Cookie 已加载"
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
