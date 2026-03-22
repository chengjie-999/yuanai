import os
import importlib
from langchain_core.tools import BaseTool


# 自动加载tools目录下所有工具的核心函数
def load_all_tools():
    """扫描tools目录下所有.py文件，自动加载所有@tool装饰的工具"""
    tools = []
    # 获取当前目录（tools）下的所有.py文件
    tool_files = [f for f in os.listdir(os.path.dirname(__file__))
                  if f.endswith('.py') and not f.startswith('__')]

    # 遍历每个工具文件，导入并收集工具
    for file in tool_files:
        # 导入模块（如 tools.weather、tools.calculator）
        module_name = f"yuanai.tools.{file[:-3]}"  # 去掉.py后缀
        module = importlib.import_module(module_name)

        # 遍历模块中的所有属性，收集@tool装饰的工具
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            # 判断是否是LangChain的Tool对象
            if isinstance(attr, BaseTool):
                tools.append(attr)

    return tools


# 对外暴露加载后的工具列表
all_tools = load_all_tools()