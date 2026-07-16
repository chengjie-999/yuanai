TOOL_CATEGORY = "stats"

from langchain_core.tools import tool
from yuanai_core.pure.stats import get_system_stats as _get_stats


@tool
def get_system_stats() -> str:
    """Get system statistics: users, sessions, messages, storage."""
    return _get_stats()
