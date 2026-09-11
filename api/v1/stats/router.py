from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from db.session import get_db

router = APIRouter(prefix="/stats", tags=["stats"])


class VisitReport(BaseModel):
    path: str = Field("/", max_length=200, description="访问的页面路径")


@router.post("/visit")
def report_visit(req: VisitReport, request: Request):
    """前端埋点：记录一次页面访问（公开路径，走全局限流）"""
    from api.v1.ratelimit import get_client_ip
    from db.session import VisitLog
    db = get_db()
    sess = db.Session()
    try:
        sess.add(VisitLog(
            path=req.path[:200],
            ip=get_client_ip(request)[:64],
            user_agent=(request.headers.get("User-Agent", "") or "")[:300],
        ))
        sess.commit()
        return {"ok": True}
    finally:
        sess.close()


@router.get("/all")
async def get_all_stats():
    """获取系统综合统计数据"""
    db = get_db()
    return db.get_stats()
