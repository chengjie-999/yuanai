from langchain_core.tools import tool
from spiderlx.core.browser_manager import browser_manager
from agent.tools.errors import classify_error


@tool
def get_browser_status() -> str:
    """检查浏览器是否存活，返回运行状态和当前页面信息"""
    try:
        if not browser_manager.running:
            return "❌ 浏览器未启动"
        return f"✅ 浏览器运行中\nURL: {browser_manager.current_url}\n标题: {browser_manager.current_title}"
    except Exception as e:
        return classify_error(e, "获取状态失败")


@tool
def get_current_url() -> str:
    """获取浏览器当前页面的 URL"""
    try:
        url = browser_manager.current_url
        if not url:
            return "❌ 浏览器未启动或无页面"
        return f"当前 URL: {url}"
    except Exception as e:
        return classify_error(e, "获取 URL 失败")


@tool
def take_browser_screenshot() -> str:
    """
    截取浏览器当前页面的截图，返回 base64 图片数据。
    比 take_screenshot 更精准，只截取网页内容，不包含浏览器 chrome。
    """
    try:
        import base64
        png = browser_manager.screenshot()
        b64 = base64.b64encode(png).decode()
        return f"截图成功，data:image/png;base64,{b64}"
    except RuntimeError as e:
        return f"❌ [致命] {e}"
    except Exception as e:
        return classify_error(e, "截图失败")
