from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from db.session import get_db

router = APIRouter(prefix="/stats", tags=["stats"])


class VisitReport(BaseModel):
    path: str = Field("/", max_length=200, description="访问的页面路径")


@router.post("/visit")
def report_visit(req: VisitReport, request: Request):
    """前端埋点：记录一次页面访问（公开路径，走全局限流）。

    用户维度分析：带 Authorization 头则解析 user_id 关联登录用户（游客=0），
    登录后页面的路由级埋点与公开页共用本端点。
    """
    from api.v1.ratelimit import get_client_ip

    user_id = 0
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        from api.v1.auth.utils import verify_token
        payload = verify_token(auth[7:])
        if payload:
            user_id = int(payload.get("user_id") or 0)

    get_db().record_visit(req.path, get_client_ip(request),
                          request.headers.get("User-Agent", "") or "", user_id)
    return {"ok": True}


@router.get("/all")
async def get_all_stats():
    """获取系统综合统计数据"""
    db = get_db()
    return db.get_stats()
