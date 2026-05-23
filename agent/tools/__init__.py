"""Agent 工具自动发现 + 通用工具合并"""

import os
import logging
import importlib

from langchain_core.tools import BaseTool
from yuanai_core.tools import all_tools as shared_tools

logger = logging.getLogger(__name__)


def load_agent_tools():
    """递归扫描 agent/tools/ 目录，加载所有 @tool 装饰的工具，拼上通用工具"""
    tools = list(shared_tools)
    seen_names = {t.name for t in tools}
    base_dir = os.path.dirname(__file__)

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith('__') and not d.startswith('.'))
        for file in sorted(files):
            if file.endswith('.py') and not file.startswith('__'):
                rel_path = os.path.relpath(os.path.join(root, file), base_dir)
                module_path = rel_path[:-3].replace(os.sep, '.')
                module_name = f"agent.tools.{module_path}"

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

    logger.info("Agent 工具已加载: %d 个（共享 %d + 专用 %d）",
                len(tools), len(shared_tools), len(tools) - len(shared_tools))
    return tools


# 模块级单例
all_agent_tools = load_agent_tools()
