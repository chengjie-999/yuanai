"""工具模块静态注册清单（打包兼容，2026-10-17）

PyInstaller 只做静态 import 追踪，os.walk 动态发现在 frozen exe 里扫不到
模块 → all_tools 为空。本文件用字面量 import 登记全部工具模块：
- frozen（exe）：__init__ 只走本清单
- 开发模式：__init__ 走 os.walk 补扫，磁盘上有但未登记的模块会 warning
  （test/test_tools_registry.py 是守门员，防漏登记）

新增工具模块：在此登记一行 import 即可，spec 无需改动。
"""

from yuanai_core.tools import (  # noqa: F401
    calculator,
    convert_tools,
    crawl_tools,
    data_tools,
    datetime_tools,
    file_tools,
    knowledge_tool,
    plan_tools,
    planet_tool,
    pubmed_tools,
    stats_tool,
    text_tools,
    ui_tools,
    user_memory,
    weather,
    web_search,
)

# 登记模块列表（__init__ 遍历加载其中的 BaseTool 实例）
TOOL_MODULES = [
    calculator,
    convert_tools,
    crawl_tools,
    data_tools,
    datetime_tools,
    file_tools,
    knowledge_tool,
    plan_tools,
    planet_tool,
    pubmed_tools,
    stats_tool,
    text_tools,
    ui_tools,
    user_memory,
    weather,
    web_search,
]
