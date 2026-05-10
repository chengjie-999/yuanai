import os
import logging
import importlib
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


def load_all_tools():
    """递归扫描 tools 目录下所有 .py 文件，自动加载所有 @tool 装饰的工具（包括子文件夹）"""
    tools = []
    seen_names = set()
    base_dir = os.path.dirname(__file__)

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith('__') and not d.startswith('.'))
        for file in sorted(files):
            if file.endswith('.py') and not file.startswith('__'):
                rel_path = os.path.relpath(os.path.join(root, file), base_dir)
                module_path = rel_path[:-3].replace(os.sep, '.')
                module_name = f"yuanai.tools.{module_path}"

                try:
                    module = importlib.import_module(module_name)
                    for attr_name in sorted(dir(module)):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, BaseTool):
                            if attr.name not in seen_names:
                                seen_names.add(attr.name)
                                tools.append(attr)
                except Exception as e:
                    logger.warning("导入工具模块 %s 失败: %s", module_name, e)

    logger.info("已加载 %d 个工具", len(tools))
    return tools


all_tools = load_all_tools()
