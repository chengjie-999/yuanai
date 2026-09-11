"""后台管理 — 用户维度：列表/冻结/创建/删除"""

from datetime import datetime, timedelta
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request
from db.session import get_db
from api.v1.middleware import require_admin

router = APIRouter(tags=["admin"])  # 无 prefix：由主 router 统一加 /admin


class FreezeRequest(BaseModel):
    user_id: int
    days: int


class AdminCreateUser(BaseModel):
    username: str
    password: str
    role: str = 'user'


@router.get("/users")
async def list_users(request: Request):
    require_admin(request)
    db = get_db()
    from db.session import User
    sess = db.Session()
    try:
        users = sess.query(User).order_by(User.id).all()
        now = datetime.utcnow()
        return [{
            "id": u.id, "username": u.username, "display_name": u.display_name or "",
            "role": u.role,
            "frozen": u.frozen_until is not None and u.frozen_until > now,
            "frozen_until": str(u.frozen_until)[:19] if u.frozen_until else None,
            "create_time": str(u.create_time)[:19] if u.create_time else "",
        } for u in users]
    finally:
        sess.close()


@router.post("/users/freeze")
async def freeze_user(req: FreezeRequest, request: Request):
    require_admin(request)
    if req.days < 0:
        raise HTTPException(status_code=400, detail="天数不能为负数")
    db = get_db()
    from db.session import User
    sess = db.Session()
    try:
        user = sess.query(User).filter_by(id=req.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user.role == "admin":
            raise HTTPException(status_code=400, detail="不能冻结管理员")
        if req.days == 0:
            user.frozen_until = None
            msg = f"已解冻用户 {user.username}"
        else:
            user.frozen_until = datetime.utcnow() + timedelta(days=req.days)
            msg = f"已冻结用户 {user.username} {req.days} 天"
        sess.commit()
        return {"ok": True, "message": msg}
    finally:
        sess.close()


@router.post("/users/create")
async def admin_create_user(req: AdminCreateUser, request: Request):
    """管理员创建新用户"""
    require_admin(request)
    db = get_db()
    result = db.register_user(req.username, req.password, role=req.role)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/users/{user_id}")
async def admin_delete_user(user_id: int, request: Request):
    """删除普通用户（仅 admin，不能删除 admin 和自己）"""
    require_admin(request)
    if user_id == getattr(request.state, "user_id", 0):
        raise HTTPException(status_code=400, detail="不能删除自己")
    from db.session import User
    db = get_db()
    sess = db.Session()
    try:
        user = sess.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user.role == "admin":
            raise HTTPException(status_code=400, detail="不能删除管理员")
        sess.delete(user)
        sess.commit()
        return {"ok": True, "deleted": user.username}
    finally:
        sess.close()
