"""系统统计查询 — 只读，无副作用。"""
from typing import Dict


def get_system_stats() -> Dict:
    """
    查询系统统计数据，返回 dict:
      {users, sessions, messages, task_images, cache_size_mb, excel_files}
    """
    from db.session import get_db

    db = get_db()
    return db.get_stats()
