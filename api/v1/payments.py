# -*- coding: utf-8 -*-
"""盈利 MVP 充值链路（2026-11-06 用户拍板最终流程）

流程：选择金额 → 前端展示收款码（本地状态）→ 填尾号备注 → **提交订单**
（此时才创建订单并发送管理员）→ 管理员确认（交易达成，不可取消）。
中间（提交后/确认前）用户可取消订单——取消会告知管理员（队列历史区可见）。
可点击查看订单信息（详情端点）。

端点：
- POST /auth/payments          提交订单：创建 pending（提交成功才创建并发送管理员）
- GET  /auth/payments          我的充值记录（含状态）
- GET  /auth/payments/{pid}    订单详情（归属校验）
- POST /auth/payments/{pid}/cancel  取消订单（pending → cancelled；告知管理员）
- POST /admin/payment-qr       管理员上传收款码图片（data/payment_qr.png）
- GET  /payment-qr             公开收款码（收款码本就公开展示，无敏感信息）

后台确认/驳回与待确认队列在 admin/users.py（require_admin 模块内聚）。
"""
import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from utils.data_path import root_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["payments"])

PAY_AMOUNTS = (10, 50, 100)   # 充值档位（固定档对账简单）
_QR_PATH = os.path.join(root_path(), "data", "payment_qr.png")
_QR_MAX_BYTES = 2 * 1024 * 1024


class PaymentCreate(BaseModel):
    amount: float = Field(..., gt=0)
    # 对账凭证：转账账号尾号（金额=订单金额系统已知、时间=提交时间系统记录）
    tail: str = Field(..., min_length=3, max_length=20, description="转账账号尾号（如 8888）")
    note: str = Field("", max_length=100, description="补充备注（选填）")


@router.post("/auth/payments")
async def create_payment(req: PaymentCreate, request: Request):
    """提交订单（提交成功才创建订单并发送管理员——2026-11-06 用户拍板）：
    创建 status=pending，直接进入管理员确认队列。"""
    uid = getattr(request.state, "user_id", None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    amount = round(req.amount, 2)
    if amount not in PAY_AMOUNTS:
        raise HTTPException(status_code=400, detail=f"仅支持以下充值档位：{'/'.join(str(a) for a in PAY_AMOUNTS)} 元")
    tail = (req.tail or "").strip()
    note = (req.note or "").strip()
    db = get_db()
    pid = db.add_payment(uid, amount,
                         (f"尾号:{tail[:20]}" + (f" 备注:{note[:100]}" if note else ""))[:200],
                         status="pending")
    if not pid:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True, "id": pid, "amount": amount, "status": "pending",
            "message": "订单已提交，管理员对账确认后额度到账（通常几分钟内）"}


@router.post("/auth/payments/{pid}/cancel")
async def cancel_payment(pid: int, request: Request):
    """用户取消订单（pending → cancelled；确认后交易达成不可取消）。
    取消会告知管理员：队列历史区可见「已取消」。"""
    uid = getattr(request.state, "user_id", None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    r = get_db().cancel_user_payment(pid, uid)
    if r == "not_found":
        raise HTTPException(status_code=404, detail="订单不存在")
    if r == "already":
        raise HTTPException(status_code=409, detail="订单已确认或已取消，无法取消")
    return {"ok": True, "message": "订单已取消（管理员可见）"}


@router.get("/auth/payments")
async def my_payments(request: Request, limit: int = 50):
    """我的充值记录（新→旧）"""
    uid = getattr(request.state, "user_id", None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    return {"records": get_db().list_payments(uid, limit=min(limit, 200))}


@router.get("/auth/payments/{pid}")
async def payment_detail(pid: int, request: Request):
    """订单详情（可点击查看订单信息）"""
    uid = getattr(request.state, "user_id", None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    d = get_db().get_payment_detail(pid, uid)
    if not d:
        raise HTTPException(status_code=404, detail="订单不存在")
    return d


@router.post("/admin/payment-qr")
async def upload_payment_qr(request: Request):
    """管理员上传收款码（multipart 字段 qr；PIL 校验真实图片，≤2MB 原样保存）"""
    from api.v1.middleware import require_admin
    require_admin(request)
    form = await request.form()
    file = form.get("qr")
    if not file or not hasattr(file, "read"):
        raise HTTPException(status_code=400, detail="请选择图片文件（字段名 qr）")
    data = await file.read()
    if len(data) > _QR_MAX_BYTES:
        raise HTTPException(status_code=400, detail="图片过大（≤2MB）")
    try:
        from PIL import Image
        import io as _io
        img = Image.open(_io.BytesIO(data))
        img.verify()
    except Exception:
        raise HTTPException(status_code=400, detail="图片格式不支持或已损坏")
    os.makedirs(os.path.dirname(_QR_PATH), exist_ok=True)
    with open(_QR_PATH, "wb") as f:
        f.write(data)
    logger.info("收款码已更新")
    return {"ok": True, "url": "/api/v1/payment-qr"}


@router.get("/payment-qr")
async def get_payment_qr():
    """公开收款码（未配置 404——前端据此提示「请先联系管理员配置收款码」）"""
    if not os.path.isfile(_QR_PATH):
        raise HTTPException(status_code=404, detail="收款码未配置")
    return FileResponse(_QR_PATH, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=300"})


from db.session import get_db  # noqa: E402（底部导入与 auth 模块同构，避免循环）
