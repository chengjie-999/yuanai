"""Agent → 云端 HTTP 桥接（user_memory / plan_tools / knowledge_tool 共用入口）。

实现已收敛到 yuanai_core/pure/agent_remote.py（纯 stdlib，供 usage.py 等
底层模块免循环导入）；本文件仅 re-export 保持既有引用不变。
"""
from yuanai_core.pure.agent_remote import (  # noqa: F401
    read_identity, is_remote_agent, agent_http,
)
