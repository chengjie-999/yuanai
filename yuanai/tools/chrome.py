from langchain_core.tools import tool

from utils.start_chrome import start_chrome


@tool("chrome_port", description="启动 Chrome 浏览器并返回调试端口信息")
def chrome_port():
    return start_chrome()
