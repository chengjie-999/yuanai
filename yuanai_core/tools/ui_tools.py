TOOL_CATEGORY = "general"

"""界面联动工具 — 模型可自主切换明暗主题（2026-10-22）

模型调用 set_theme 后：后端 SSE 拦截 tool_start 发 theme_event → 前端
ThemeContext.setTheme 应用并持久化（localStorage + 服务端偏好）；
本工具返回值只告知模型动作已受理（真实切换由前端事件执行）。
"""
from langchain_core.tools import tool


@tool
def set_theme(theme: str) -> str:
    """切换界面明暗主题。theme 参数只能是 'dark'（暗色/深色/夜间模式）或 'light'（亮色/浅色/白天模式）。
    用户要求换深色、暗色、夜间、浅色、亮色主题时调用。"""
    if theme not in ("dark", "light"):
        return "theme 参数必须是 'dark' 或 'light'"
    return f"已将界面切换为{'暗色' if theme == 'dark' else '亮色'}模式"

@tool
def set_chat_backend(backend: str) -> str:
    """切换执行后端（云端/本机）。backend 参数只能是 'auto'（自动：本机优先，离线回退云端）、
    'cloud'（强制云端，不用本机 Agent）或 'local'（强制本机 Agent，离线会报错）。
    用户要求「切到云端」「用我的电脑执行」「恢复自动」等执行位置偏好时调用。"""
    if backend not in ("auto", "cloud", "local"):
        return "backend 参数必须是 'auto'、'cloud' 或 'local'"
    label = {"auto": "自动（本机优先）", "cloud": "云端", "local": "本机"}[backend]
    return f"已将执行后端切换为：{label}"

