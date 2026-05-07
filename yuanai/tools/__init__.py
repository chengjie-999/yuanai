import os
import importlib
from langchain_core.tools import BaseTool


def load_all_tools():
    """递归扫描 tools 目录下所有 .py 文件，自动加载所有 @tool 装饰的工具（包括子文件夹）"""
    tools = []
    base_dir = os.path.dirname(__file__)  # tools 目录的路径

    for root, dirs, files in os.walk(base_dir):
        # 忽略 __pycache__ 和隐藏目录
        dirs[:] = [d for d in dirs if not d.startswith('__') and not d.startswith('.')]
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                # 获取相对于 base_dir 的路径（例如 subdir/weather.py）
                rel_path = os.path.relpath(os.path.join(root, file), base_dir)
                # 将路径分隔符转换为点，并去掉 .py 后缀
                module_path = rel_path[:-3].replace(os.sep, '.')
                # 构造完整模块名（假设顶级包名为 yuanai.tools）
                module_name = f"yuanai.tools.{module_path}"

                try:
                    module = importlib.import_module(module_name)
                    # 收集模块中的所有 BaseTool 实例
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, BaseTool):
                            print('AI工具已更新', attr_name)
                            tools.append(attr)
                except Exception as e:
                    # 可选：打印错误便于调试
                    print(f"导入模块 {module_name} 失败: {e}")

    return tools


all_tools = load_all_tools()
