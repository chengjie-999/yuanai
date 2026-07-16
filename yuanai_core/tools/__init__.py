"""
通用工具自动发现 + 按类别筛选。

类别体系（每个工具模块顶部的 TOOL_CATEGORY）：
  general   — 通用工具（计算、天气）
  memory    — 用户记忆
  knowledge — 知识库检索
  file      — 文件操作
  stats     — 系统统计
  crawl     — 网页爬取
  data      — 数据分析

用法：
  from yuanai_core.tools import all_tools, load_tools_for

  # 获取全部 20 个共享工具
  all_tools

  # 按类别筛选
  orch_tools = load_tools_for("general", "memory", "knowledge", "file", "stats", "crawl", "data")
  crawl_tools = load_tools_for("crawl", "file")
  data_tools = load_tools_for("data", "file")
"""

import os
import logging
import importlib
from typing import List, Dict
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

# 工具名 → 类别映射表（load_all_tools 时自动填充）
_tool_category_map: Dict[str, str] = {}


def _get_module_category(module) -> str:
    """从模块中安全提取 TOOL_CATEGORY"""
    return getattr(module, 'TOOL_CATEGORY', 'general')


def load_all_tools() -> List[BaseTool]:
    """递归扫描 tools 目录，自动加载所有 @tool 装饰的工具"""
    global _tool_category_map
    tools = []
    seen_names = set()
    _tool_category_map = {}
    base_dir = os.path.dirname(__file__)

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith('__') and not d.startswith('.'))
        for file in sorted(files):
            if file.endswith('.py') and not file.startswith('__'):
                rel_path = os.path.relpath(os.path.join(root, file), base_dir)
                module_path = rel_path[:-3].replace(os.sep, '.')
                module_name = f"yuanai_core.tools.{module_path}"

                try:
                    module = importlib.import_module(module_name)
                    cat = _get_module_category(module)
                    for attr_name in sorted(dir(module)):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, BaseTool):
                            if attr.name not in seen_names:
                                seen_names.add(attr.name)
                                tools.append(attr)
                                _tool_category_map[attr.name] = cat
                except Exception as e:
                    logger.warning("导入工具模块 %s 失败: %s", module_name, e)

    logger.info("已加载 %d 个共享工具，类别分布: %s",
                len(tools),
                {c: sum(1 for v in _tool_category_map.values() if v == c)
                 for c in set(_tool_category_map.values())})
    return tools


def load_tools_for(*categories: str) -> List[BaseTool]:
    """按类别加载共享工具。不指定类别则返回全部。

    Args:
        categories: 一个或多个 TOOL_CATEGORY，如 "crawl", "data", "general"

    Returns:
        匹配类别的工具列表
    """
    all_t = load_all_tools()

    if not categories:
        return all_t

    category_set = set(categories)
    filtered = [t for t in all_t if _tool_category_map.get(t.name, 'general') in category_set]

    logger.info("按类别 %s 筛选出 %d/%d 个工具", categories, len(filtered), len(all_t))
    return filtered


# 模块级单例：全部 20 个共享工具
all_tools = load_all_tools()
