from langchain_core.tools import tool


@tool
def xiao_yuan_tool() -> str:
    """
    小猿众包工具
    """
    return "✅ 小猿众包工具已加载，可以使用相关功能了！"
