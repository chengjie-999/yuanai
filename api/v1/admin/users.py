"""后台管理 — 用户维度：列表/冻结/创建/删除"""

from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request
from db.session import get_db
from api.v1.middleware import require_admin

router = APIRouter(tags=["admin"])  # 无 prefix：由主 router 统一加 /admin


class FreezeRequest(BaseModel):
    user_id: int
    days: int
    reason: str = ""  # C7（2026-10-29）：冻结原因，登录时向用户展示


class AdminCreateUser(BaseModel):
    # 校验与登录口径一致（2026-10-30 修复）：密码 <8 位或用户名 <3 字符的账号
    # 在登录端会被拒绝——此前管理员可创建出「永远登不上」的用户
    username: str = Field(..., min_length=3, max_length=50, description="用户名（至少 3 个字符）")
    password: str = Field(..., min_length=8, max_length=64, description="密码（至少 8 个字符）")
    role: str = 'user'


@router.get("/users")
async def list_users(request: Request):
    require_admin(request)
    db = get_db()
    from db.session import User, TokenUsage
    with db.session() as sess:
        users = sess.query(User).order_by(User.id).all()
        # 每用户累计成本（2026-10-30 用户管理成本列）：按 (user, model) 聚合后折算
        from sqlalchemy import func as _func
        from yuanai_core.usage import model_cost
        from config.settings import COST_PROFIT_MULTIPLIER
        cost_rows = (sess.query(TokenUsage.user_id, TokenUsage.model,
                                _func.sum(TokenUsage.prompt_tokens),
                                _func.sum(TokenUsage.completion_tokens),
                                _func.count(TokenUsage.id))
                     .group_by(TokenUsage.user_id, TokenUsage.model).all())
        by_uid = {}
        for r in cost_rows:
            e = by_uid.setdefault(int(r[0] or 0), {"cost": 0.0, "calls": 0})
            e["cost"] += model_cost(r[1], int(r[2] or 0), int(r[3] or 0), calls=int(r[4] or 1))
            e["calls"] += int(r[4] or 0)
        now = datetime.utcnow()
        return [{
            "id": u.id, "username": u.username, "display_name": u.display_name or "",
            "role": u.role,
            "frozen": u.frozen_until is not None and u.frozen_until > now,
            "frozen_until": str(u.frozen_until)[:19] if u.frozen_until else None,
            "freeze_reason": u.freeze_reason or "",
            "create_time": str(u.create_time)[:19] if u.create_time else "",
            # 财务口径（2026-10-30）：实际成本 + 系数成本（=成本×系数，应计）+
            # 收款金额；显示金额 = 系数成本 − 收款（前端计算）
            "cost": round(by_uid.get(u.id, {}).get("cost", 0), 4),
            # 系数成本保留实际精度（round 6 去浮点噪声），显示金额 = 系数成本 − 收款
            # 由前端用实际值计算后再格式化（2026-10-30：计算不用显示取整值）
            "billed": round(by_uid.get(u.id, {}).get("cost", 0) * COST_PROFIT_MULTIPLIER, 6),
            "calls": by_uid.get(u.id, {}).get("calls", 0),
            "paid": float(u.paid_amount or 0),
            "multiplier": COST_PROFIT_MULTIPLIER,
        } for u in users]
@router.post("/users/revoke-tokens")
async def revoke_user_tokens(req: FreezeRequest, request: Request):
    """吊销用户全部 JWT（token_version +1，旧 token 立即失效；S3.4 M7）"""
    require_admin(request)
    db = get_db()
    from db.session import User
    with db.session() as sess:
        user = sess.query(User).filter_by(id=req.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        user.token_version = (user.token_version or 0) + 1
        sess.commit()
        return {"ok": True, "token_version": user.token_version,
                "message": f"用户 {user.username} 的全部登录令牌已失效"}
@router.post("/users/freeze")
async def freeze_user(req: FreezeRequest, request: Request):
    require_admin(request)
    if req.days < 0:
        raise HTTPException(status_code=400, detail="天数不能为负数")
    db = get_db()
    from db.session import User
    with db.session() as sess:
        user = sess.query(User).filter_by(id=req.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user.role == "admin":
            raise HTTPException(status_code=400, detail="不能冻结管理员")
        if req.days == 0:
            user.frozen_until = None
            user.freeze_reason = ""  # 解冻清原因
            msg = f"已解冻用户 {user.username}"
        else:
            user.frozen_until = datetime.utcnow() + timedelta(days=req.days)
            user.freeze_reason = (req.reason or "").strip()[:500]
            msg = f"已冻结用户 {user.username} {req.days} 天"
        sess.commit()
        return {"ok": True, "message": msg}
@router.post("/users/create")
async def admin_create_user(req: AdminCreateUser, request: Request):
    """管理员创建新用户"""
    require_admin(request)
    db = get_db()
    result = db.register_user(req.username, req.password, role=req.role)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class ResetPasswordBody(BaseModel):
    password: str = Field(..., min_length=8, max_length=64, description="新密码（最少 8 位）")


@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(user_id: int, body: ResetPasswordBody, request: Request):
    """管理员重置用户密码（2026-10-30）：密码 bcrypt 单向哈希无法反解显示，
    忘记密码的账号由管理员直接重置。重置后 token_version+1 吊销旧会话。"""
    require_admin(request)
    db = get_db()
    from db.session import User
    import bcrypt as _bcrypt
    with db.session() as sess:
        user = sess.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user.role == "admin":
            raise HTTPException(status_code=400, detail="不能重置管理员密码")
        user.password_hash = _bcrypt.hashpw(body.password.encode(), _bcrypt.gensalt()).decode()
        user.token_version = (user.token_version or 0) + 1
        sess.commit()
        return {"ok": True, "message": f"已重置用户 {user.username} 的密码（旧登录会话已失效）"}


class PaidAmountBody(BaseModel):
    amount: float = Field(..., ge=0, description="收款金额（元，≥0，两位小数）")


@router.post("/users/{user_id}/paid")
async def admin_set_paid(user_id: int, body: PaidAmountBody, request: Request):
    """收款金额登记（2026-10-30）：线下收款，管理员手动填写/更新"""
    require_admin(request)
    db = get_db()
    from decimal import Decimal
    amount = round(Decimal(str(body.amount)), 2)
    if not db.set_user_paid(user_id, float(amount)):
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True, "message": f"已登记收款金额 ¥{amount:.2f}"}


@router.delete("/users/{user_id}")
async def admin_delete_user(user_id: int, request: Request):
    """删除普通用户（仅 admin，不能删除 admin 和自己）"""
    require_admin(request)
    if user_id == getattr(request.state, "user_id", 0):
        raise HTTPException(status_code=400, detail="不能删除自己")
    from db.session import User
    db = get_db()
    with db.session() as sess:
        user = sess.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user.role == "admin":
            raise HTTPException(status_code=400, detail="不能删除管理员")
        sess.close()
        # C4（2026-10-29）：级联删除全部个人数据（会话/消息/记忆/数据集/
        # 星球/计划/日志/文件/Milvus + 设备解绑）——不再只删 users 行
        summary = db.delete_user_cascade(user_id)
        return {"ok": True, "deleted": user.username, **summary}