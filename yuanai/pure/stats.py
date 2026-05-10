"""系统统计查询 — 只读。"""
from typing import Dict


def get_system_stats() -> Dict:
    """查询数据库统计，返回 {users, sessions, messages, ...}。"""
    from db.session import get_db
    db = get_db()
    return db.get_stats()
