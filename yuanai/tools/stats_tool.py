from langchain_core.tools import tool


@tool
def get_system_stats() -> str:
    """
    获取系统综合统计数据，包括用户数、聊天会话数、消息数、审核记录数、缓存大小、数据文件列表等。
    当用户询问系统使用情况、数据统计、有多少用户/会话/消息时调用此工具。
    """
    try:
        from db.session import get_db
        db = get_db()
        stats = db.get_stats()
        lines = [
            f"📊 系统数据统计",
            f"━━━━━━━━━━━━━━━━━━",
            f"👤 用户数：{stats['users']}",
            f"💬 聊天会话：{stats['sessions']}（共 {stats['messages']} 条消息，平均每会话 {stats['avg_messages_per_session']} 条）",
            f"🖼 审核记录：{stats['task_images']}",
            f"📦 截图缓存：{stats['cache_size_mb']} MB",
        ]
        files = stats.get('excel_files', [])
        if files:
            lines.append(f"📁 数据文件（{len(files)} 个）：")
            for f in files[:10]:
                lines.append(f"  · {f['name']}（{f['size_kb']} KB）")
            if len(files) > 10:
                lines.append(f"  ... 共 {len(files)} 个文件")
        return '\n'.join(lines)
    except Exception as e:
        return f"获取统计失败：{str(e)}"
