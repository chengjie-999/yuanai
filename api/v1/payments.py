# -*- coding: utf-8 -*-
"""盈利 MVP 充值链路（2026-11-06，零资质阶段 0：个人收款码 + 人工确认）

- POST /auth/payments：创建充值订单（档位金额）→ status=pending
- POST /auth/payments/{pid}/submit：用户转账后提交转账信息（金额/尾号/时间）
- GET  /auth/payments：我的充值记录（含状态）
- POST /admin/payment-qr：管理员上传收款码图片（data/payment_qr.png）
- GET  /payment-qr：公开收款码（收款码本就公开展示，无敏感信息）

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


class PaymentSubmit(BaseModel):
    # 对账凭证：转账账号尾号（金额=订单金额系统已知、时间=提交时间系统记录，
    # 用户只需填尾号——2026-11-06 用户拍板）
    tail: str = Field(..., min_length=3, max_length=20, description="转账账号尾号（如 8888）")
    note: str = Field("", max_length=100, description="补充备注（选填）")


@router.post("/auth/payments")
async def create_payment(req: PaymentCreate, request: Request):
    """创建充值订单（pending）：选档位 → 得到订单号 → 扫码转账 → submit 填信息"""
    uid = getattr(request.state, "user_id", None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    amount = round(req.amount, 2)
    if amount not in PAY_AMOUNTS:
        raise HTTPException(status_code=400, detail=f"仅支持以下充值档位：{'/'.join(str(a) for a in PAY_AMOUNTS)} 元")
    db = get_db()
    # created = 订单已生成但用户尚未提交转账（不进管理员确认队列——2026-11-06
    # 用户拍板「等他提交订单再发送订单确认」）；提交后 → pending 才出现在队列
    pid = db.add_payment(uid, amount, "", status="created")
    if not pid:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True, "id": pid, "amount": amount, "status": "created",
            "qr": "/api/v1/payment-qr",
            "message": "请使用微信/支付宝扫描收款码转账，完成后在下方提交转账信息"}


@router.post("/auth/payments/{pid}/submit")
async def submit_payment(pid: int, req: PaymentSubmit, request: Request):
    """转账后提交信息（转账金额/尾号/时间）——管理员据此对账确认"""
    uid = getattr(request.state, "user_id", None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    from db.session import PaymentRecord
    db = get_db()
    with db.session() as sess:
        p = sess.query(PaymentRecord).filter_by(id=pid, user_id=uid).first()
        if not p:
            raise HTTPException(status_code=404, detail="订单不存在")
        if p.status not in ("created", "pending"):
            raise HTTPException(status_code=400, detail="该订单已处理，请重新生成订单")
        tail = (req.tail or "").strip()
        note = (req.note or "").strip()
        p.note = (f"尾号:{tail[:20]}" + (f" 备注:{note[:100]}" if note else ""))[:200]
        # 提交转账信息 → 进入管理员确认队列
        p.status = "pending"
        sess.commit()
    return {"ok": True, "message": "已提交，管理员对账确认后额度到账（通常几分钟内）"}


@router.get("/auth/payments")
async def my_payments(request: Request, limit: int = 50):
    """我的充值记录（新→旧）"""
    uid = getattr(request.state, "user_id", None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    return {"records": get_db().list_payments(uid, limit=min(limit, 200))}


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
