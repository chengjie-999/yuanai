from langchain_core.tools import tool


@tool
def xiao_yuan_tool() -> str:
    """
    使用小猿众包自动化工具。前提条件：成功打开网站并完成登陆
    """
    return "✅ 小猿众包工具已加载，可以使用相关功能了！"
