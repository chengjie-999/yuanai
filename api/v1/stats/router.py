from fastapi import APIRouter
from db.session import get_db

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/all")
async def get_all_stats():
    """获取系统综合统计数据"""
    db = get_db()
    return db.get_stats()
