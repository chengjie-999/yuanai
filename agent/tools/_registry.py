"""Agent 专用工具模块静态注册清单（打包兼容，2026-10-17）

与 yuanai_core/tools/_registry.py 同构：PyInstaller 静态追踪字面量 import；
frozen（exe）模式 __init__ 只走本清单，开发模式 os.walk 补扫 + 未登记告警。
新增专用工具模块：在此登记一行即可，spec 无需改动。
"""

from agent.tools import (  # noqa: F401
    audit_tools,
    browser_info_tools,
    claude_delegate,
    cookie_tools,
    monitor_tools,
    selenium_tools,
)
from agent.tools.selenium_tools import core as selenium_core, xiaoyuan as selenium_xiaoyuan  # noqa: F401

TOOL_MODULES = [
    audit_tools,
    browser_info_tools,
    claude_delegate,
    cookie_tools,
    monitor_tools,
    selenium_tools,
    selenium_core,
    selenium_xiaoyuan,
]
