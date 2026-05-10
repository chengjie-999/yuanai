from langchain_core.tools import tool
from yuanai.pure.stats import get_system_stats as _get_stats


@tool
def get_system_stats() -> str:
    """获取系统综合统计数据（用户数、会话数、消息数、审核记录、缓存大小）。"""
    try:
        stats = _get_stats()
        lines = [
            f"\U0001f4ca 系统数据统计",
            f"━━━━━━━━━━━━━━━━━",
            f"\U0001f464 用户数：{stats['users']}",
            f"\U0001f4ac 聊天会话：{stats['sessions']}（共 {stats['messages']} 条消息）",
            f"\U0001f5bc 审核记录：{stats['task_images']}",
            f"\U0001f4e6 截图缓存：{stats['cache_size_mb']} MB",
        ]
        files = stats.get('excel_files', [])
        if files:
            lines.append(f"\U0001f4c1 数据文件（{len(files)} 个）：")
            for f in files[:10]:
                lines.append(f"  · {f['name']}（{f['size_kb']} KB）")
        return '\n'.join(lines)
    except Exception as e:
        return f"获取统计失败：{str(e)}"
