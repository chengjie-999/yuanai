import json as _json
import logging
import os as _os
import re
import time
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from db.session import get_db
from api.v1.auth.utils import create_token, verify_token, create_sse_token
from api.v1.ratelimit import auth_limiter, get_client_ip
from utils.data_path import root_path as _root_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


from api.v1.models_file import read_models_file as _read_models_file, write_models_file as _write_models_file

MAX_LOGIN_ATTEMPTS = 5
LOCK_MINUTES = 15


class AuthRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def strip_username(cls, v: str) -> str:
        """自动去除用户名首尾空格"""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("用户名至少 3 个字符")
        return v

    @field_validator("password")
    @classmethod
    def check_password_length(cls, v: str) -> str:
        """密码最小长度校验"""
        if len(v) < 8:
            raise ValueError("密码至少 8 个字符")
        return v


class RegisterRequest(AuthRequest):
    display_name: str = ""
    role: str = "user"
    agreement_accepted: bool = False  # C11：协议勾选后端强制（注册即留痕 agreed_at）


@router.post("/register")
def register(req: RegisterRequest, request: Request):
    """注册新用户（2026-10-30 开放：REGISTER_OPEN 默认 true，后台可关）。

    强化（用户拍板：用户名不重复/合规/零 bug）：
    - 协议勾选后端强制（未勾选 422），注册成功即写 agreed_at
    - 用户名合规：拒绝含 admin/管理员（防冒充）+ 内容安全闸拦违规词
    - 防刷：登录限流器 + 每 IP 每日 3 账号
    - 唯一性：查重 + IntegrityError 兜底（并发同名注册不 500 不脏数据）
    """
    from config.settings import REGISTER_OPEN
    if not REGISTER_OPEN:
        raise HTTPException(status_code=403, detail="注册功能暂不开放，请联系管理员创建账号")
    if not req.agreement_accepted:
        raise HTTPException(status_code=422, detail="请先阅读并同意《用户协议》与《隐私政策》")
    ip = get_client_ip(request)
    auth_limiter.check(ip)
    from api.v1.db_helpers import consume_daily_quota
    if not consume_daily_quota(f"register:{ip}", 3):
        raise HTTPException(status_code=429, detail="注册过于频繁（每 IP 每日最多 3 个账号），请明天再试")
    # 用户名合规（2026-10-30）：防冒充 + 内容安全闸
    uname_low = req.username.lower()
    if "admin" in uname_low or "管理员" in req.username:
        raise HTTPException(status_code=400, detail="用户名不能包含 admin/管理员")
    from yuanai_core.pure.content_safety import check_content, audit_log, BLOCK_MESSAGE
    blocked, hit = check_content(req.username)
    if blocked:
        audit_log(0, "register", hit, req.username)
        raise HTTPException(status_code=400, detail=BLOCK_MESSAGE)
    db = get_db()
    result = db.register_user(req.username, req.password,
                              display_name=req.display_name or "", role="user")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    # 协议留痕（注册即接受）
    try:
        from db.session import User
        with db.session() as sess:
            u = sess.query(User).filter_by(id=result["id"]).first()
            if u and not u.agreed_at:
                u.agreed_at = datetime.utcnow()
                sess.commit()
    except Exception:
        pass
    logger.info("新用户注册: username=%s ip=%s", req.username, ip)
    return result


@router.post("/login")
def login(req: AuthRequest, request: Request):
    """用户登录（连续失败 5 次锁定 15 分钟）"""
    ip = get_client_ip(request)
    auth_limiter.check(ip)
    db = get_db()

    # 1. 检查账号是否被临时锁定
    user = db.get_user_by_username(req.username)
    if user and user.locked_until and user.locked_until > datetime.utcnow():
        remaining = int((user.locked_until - datetime.utcnow()).total_seconds())
        logger.warning("登录被锁: username=%s, ip=%s, 剩余=%ds", req.username, ip, remaining)
        raise HTTPException(
            status_code=429,
            detail=f"账号已临时锁定，请 {remaining} 秒后重试",
        )

    # 2. 验证密码
    user = db.authenticate_user(req.username, req.password)
    if not user:
        db.record_failed_login(req.username)
        # 重新读取锁定状态用于日志
        updated = db.get_user_by_username(req.username)
        attempts = updated.failed_login_attempts if updated else 0
        logger.warning(
            "登录失败: username=%s, ip=%s, attempts=%d, ua=%s",
            req.username, ip, attempts,
            request.headers.get("User-Agent", "")[:120],
        )
        if updated and updated.locked_until and updated.locked_until > datetime.utcnow():
            raise HTTPException(
                status_code=429,
                detail=f"登录失败次数过多，账号已锁定 {LOCK_MINUTES} 分钟",
            )
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 3. 管理员冻结检查（C7 2026-10-29：附冻结原因与申诉入口）
    if user.frozen_until and user.frozen_until > datetime.utcnow():
        days = (user.frozen_until - datetime.utcnow()).days
        reason = (user.freeze_reason or "").strip()
        detail = f"账号已被冻结，剩余 {days} 天"
        if reason:
            detail += f"。冻结原因：{reason}"
        detail += "。如有异议可通过申诉入口提交申诉。"
        raise HTTPException(status_code=403, detail=detail)

    # 4. 登录成功 — 重置失败计数 + 发令牌
    db.reset_login_attempts(user.id)
    if user.failed_login_attempts > 0:
        logger.info("登录成功（锁定解除）: user=%s, ip=%s", user.username, ip)
    else:
        logger.info("登录成功: user=%s, ip=%s", user.username, ip)

    token = create_token(user.id, user.role, user.username, track_session=True)
    # 并发登录数限制（2026-10-30）：登记本会话，超 5 台踢最旧（被踢设备下个请求 401）
    from api.v1.auth.utils import register_login_session
    _pl = verify_token(token) or {}
    _exp = _pl.get("exp")
    exp_ts = _exp if isinstance(_exp, (int, float)) else (
        _exp.timestamp() if hasattr(_exp, "timestamp") else time.time() + 86400)
    register_login_session(user.id, _pl.get("jti", ""), exp_ts)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "display_name": user.display_name or user.username,
            "email": user.email or "",
            "avatar": user.avatar or "",
            "has_password": bool(user.password_hash),
            "theme": user.theme or "",
        },
    }


# ===================== R1' 邮箱验证码登录（2026-11-05，注册登录合一） =====================

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


class EmailCodeRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=190)


class EmailLoginRequest(EmailCodeRequest):
    code: str = Field(..., min_length=6, max_length=6)
    agreement_accepted: bool = False  # C11：自动注册时协议勾选强制留痕


@router.post("/email-code")
async def send_email_code_endpoint(req: EmailCodeRequest, request: Request):
    """发送邮箱验证码（公开端点）。防刷护栏：SMTP 未配置 503；60s 冷却 429；
    每邮箱每日 10 条 429；错 5 次作废在验证接口。"""
    email = req.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="邮箱格式不正确")
    from api.v1.auth.email_code import smtp_configured, check_cooldown, \
        consume_send_quota, send_email_code
    if not smtp_configured():
        raise HTTPException(status_code=503, detail="邮箱验证码服务未配置，请使用用户名密码登录")
    ip = get_client_ip(request)
    auth_limiter.check(ip)
    cd = check_cooldown(email)
    if cd > 0:
        raise HTTPException(status_code=429, detail=f"发送过于频繁，请 {cd} 秒后再试")
    if not consume_send_quota(email):
        raise HTTPException(status_code=429, detail="今日验证码发送次数已达上限（10 条），请明天再试")
    try:
        result = await send_email_code(email)
    except Exception as e:
        logger.error("验证码邮件发送失败: email=%s err=%s", email, e)
        raise HTTPException(status_code=502, detail="验证码邮件发送失败，请稍后重试")
    logger.info("验证码已发送: email=%s ip=%s", email, ip)
    return {"ok": True, **result}


@router.post("/email-login")
def email_login_endpoint(req: EmailLoginRequest, request: Request):
    """邮箱验证码登录（注册登录合一，公开端点）：
    验证码正确 → 用户存在=直接登录 / 不存在=自动注册（协议勾选强制）→ 自动登录。"""
    email = req.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="邮箱格式不正确")
    ip = get_client_ip(request)
    auth_limiter.check(ip)
    from api.v1.auth.email_code import email_login
    result = email_login(email, req.code.strip(), req.agreement_accepted)
    if "error" in result:
        status = 422 if result.get("agreement_required") else (
            403 if result.get("frozen") else 401)
        raise HTTPException(status_code=status, detail=result["error"])
    return {
        "token": result["token"],
        "is_new": result["is_new"],
        "user": {
            "id": result["user_id"],
            "username": result["username"],
            "display_name": result["display_name"],
            "email": email,
            "avatar": result.get("avatar", ""),
            "has_password": result.get("has_password", False),
            "role": "user",
            "theme": "",
        },
    }


class AppealRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    contact: str = Field("", max_length=200)
    reason: str = Field(..., min_length=1, max_length=500)


@router.post("/appeal")
def submit_appeal(req: AppealRequest, request: Request):
    """C7 冻结申诉（2026-10-29，公开端点——被冻结用户无法登录）：
    落申诉工单（kind=appeal），管理员在后台「举报工单」Tab 处理。
    护栏：每 IP 每日 3 次（Redis 24h 计数，故障放行）；仅冻结账号可申诉。"""
    ip = get_client_ip(request)
    db = get_db()
    # 先校验（404/400 不消耗配额——探测请求不占申诉额度），仅有效申诉计次数
    user = db.get_user_by_username(req.username.strip())
    if not user:
        raise HTTPException(status_code=404, detail="账号不存在")
    from datetime import datetime as _dt
    if not (user.frozen_until and user.frozen_until > _dt.utcnow()):
        raise HTTPException(status_code=400, detail="账号当前未被冻结，无需申诉")
    from api.v1.db_helpers import consume_daily_quota
    if not consume_daily_quota(f"appeal:{ip}", 3):
        raise HTTPException(status_code=429, detail="申诉提交过于频繁，请明天再试")
    db.add_appeal(user.id, req.reason, req.contact)
    logger.info("冻结申诉已提交: user=%s ip=%s", req.username, ip)
    return {"ok": True, "message": "申诉已提交，平台将在 3 个工作日内通过您留的联系方式反馈处理结果"}


@router.get("/cost")
def my_cost(request: Request):
    """用户本人 API 成本（2026-10-30）：本月 30 天/累计，计费价 = 成本 × 盈利系数。
    真实成本为平台内部口径，普通用户不返回（2026-10-30 用户拍板）；admin 保留
    （后台成本分析同口径）。"""
    uid = getattr(request.state, "user_id", None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    from config.settings import ARREARS_LIMIT, COST_PROFIT_MULTIPLIER
    data = get_db().query_user_cost(uid)
    is_admin = getattr(request.state, "role", "") == "admin"
    # 盈利系数快照（2026-10-30）：billed 由 query_user_cost 按写入时系数锁定计算，
    # 改系数只影响新消费；计算全程实际精度（round 6 仅去浮点噪声）
    billed_total = data["billed_total"]
    # 累计收款（2026-10-30 逐笔记账）：线下收款管理员登记，各笔之和
    paid = 0.0
    try:
        paid = round(get_db().user_paid_totals([uid]).get(uid, 0.0), 2)
    except Exception:
        pass
    out = {
        "billed_month": data["billed_month"],
        "billed_total": billed_total,
        "paid": paid,
        "outstanding": round(billed_total - paid, 6),
        "arrears_limit": ARREARS_LIMIT,  # 欠费限制门槛（前端提示用）
        "month_calls": data["month_calls"],
        "total_calls": data["total_calls"],
    }
    if is_admin:
        out["month_cost"] = data["month_cost"]
        out["total_cost"] = data["total_cost"]
        out["multiplier"] = COST_PROFIT_MULTIPLIER
    return out


@router.post("/agree")
def agree_terms(request: Request):
    """C11（2026-10-29）：记录《用户协议》《隐私政策》接受时间（登录勾选留痕）。
    软记录不硬拦截——避免破坏 API 直调客户端；前端登录勾选强制 + 此处留痕。"""
    user_id = getattr(request.state, "user_id", 0)
    if user_id:
        db = get_db()
        with db.session() as sess:
            from db.session import User
            u = sess.query(User).filter_by(id=user_id).first()
            if u and not u.agreed_at:
                u.agreed_at = datetime.utcnow()
                sess.commit()
    return {"ok": True}


class ThemeUpdate(BaseModel):
    theme: str  # 'light' | 'dark'


@router.get("/theme")
def get_theme(request: Request):
    """获取用户主题偏好"""
    db = get_db()
    uid = getattr(request.state, 'user_id', None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    return {"theme": db.get_user_theme(uid)}


@router.put("/theme")
def update_theme(req: ThemeUpdate, request: Request):
    """更新用户主题偏好"""
    if req.theme not in ('light', 'dark'):
        raise HTTPException(status_code=400, detail="theme 必须为 light 或 dark")
    uid = getattr(request.state, 'user_id', None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    db = get_db()
    ok = db.update_user_theme(uid, req.theme)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True, "theme": req.theme}


class ProfileUpdate(BaseModel):
    display_name: str = ""


class PasswordUpdate(BaseModel):
    # R1'（2026-11-06）：邮箱注册用户无密码——设置密码时 old_password 可空
    old_password: str = ""
    # 与登录校验同口径（2026-10-30）：<8 位的新密码改完就登不上，端点层直接拒
    new_password: str = Field(..., min_length=8, max_length=64)


@router.put("/profile")
def update_profile(req: ProfileUpdate, request: Request):
    """更新个人信息（显示名称）"""
    uid = getattr(request.state, 'user_id', None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    if not req.display_name.strip():
        raise HTTPException(status_code=400, detail="显示名称不能为空")
    db = get_db()
    ok = db.update_display_name(uid, req.display_name.strip())
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True, "display_name": req.display_name.strip()}


@router.put("/password")
def update_password(req: PasswordUpdate, request: Request):
    """修改/设置密码（R1' 两态，2026-11-06）：
    邮箱注册用户无密码 → 首次设置（old_password 忽略）；
    已有密码 → 必须校验原密码。改密后 token_version+1 全部旧会话失效。"""
    uid = getattr(request.state, 'user_id', None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    db = get_db()
    ok, err = db.change_password(uid, req.old_password or "", req.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"ok": True}


# ===================== 用户头像（2026-11-06 用户拍板：可上传图片作头像） =====================

_AVATAR_DIR = _os.path.join(_root_path(), "data", "user_avatars")
_AVATAR_MAX_BYTES = 2 * 1024 * 1024   # 2MB 上限
_AVATAR_SIZE = 256                    # 统一压缩到 256x256


@router.post("/avatar")
async def upload_avatar(request: Request):
    """上传头像（登录用户，multipart file 字段名 avatar）：
    PIL 校验真实图片 → 压缩到 256x256 PNG → data/user_avatars/{uid}.png →
    users.avatar 存带版本参数的公开 URL（缓存刷新）。"""
    uid = getattr(request.state, 'user_id', None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    form = await request.form()
    file = form.get("avatar")
    # 注意：request.form() 返回 starlette.datastructures.UploadFile，与
    # fastapi.datastructures.UploadFile 不同类（新版 FastAPI 拆分）——
    # isinstance 必失败，用鸭子类型判断
    if not file or not hasattr(file, "read"):
        raise HTTPException(status_code=400, detail="请选择图片文件（字段名 avatar）")
    data = await file.read()
    if len(data) > _AVATAR_MAX_BYTES:
        raise HTTPException(status_code=400, detail="图片过大（≤2MB）")
    try:
        from PIL import Image
        import io as _io
        img = Image.open(_io.BytesIO(data))
        img.verify()  # 真实图片校验（防伪装文件）
        img = Image.open(_io.BytesIO(data))
        img = img.convert("RGB")
        img.thumbnail((_AVATAR_SIZE, _AVATAR_SIZE))
    except Exception:
        raise HTTPException(status_code=400, detail="图片格式不支持或已损坏（支持 jpg/png/webp 等常见格式）")
    _os.makedirs(_AVATAR_DIR, exist_ok=True)
    img.save(_os.path.join(_AVATAR_DIR, f"{uid}.png"), "PNG")
    import time as _time
    # auth 路由前缀 /auth → 公开路径 /api/v1/auth/user-avatar/{uid}（middleware 白名单）
    avatar_url = f"/api/v1/auth/user-avatar/{uid}?v={int(_time.time())}"
    db = get_db()
    with db.session() as sess:
        from db.session import User
        u = sess.query(User).filter_by(id=uid).first()
        if not u:
            raise HTTPException(status_code=404, detail="用户不存在")
        u.avatar = avatar_url
        sess.commit()
    logger.info("头像已更新: user=%s", uid)
    return {"ok": True, "avatar": avatar_url}


@router.get("/user-avatar/{uid}")
def get_user_avatar(uid: int):
    """头像公开端点（uid 整数白名单天然防穿越；PNG 统一格式）"""
    if uid <= 0 or uid > 10 ** 9:
        raise HTTPException(status_code=404, detail="头像不存在")
    path = _os.path.join(_AVATAR_DIR, f"{uid}.png")
    if not _os.path.isfile(path):
        raise HTTPException(status_code=404, detail="头像不存在")
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type="image/png")


# ===================== 长期记忆（透明可编辑） =====================

class MemoryUpdate(BaseModel):
    memory: str


def _normalize_memory(text: str) -> str:
    """记忆文本归一化：\r\n→\n、逐行 strip、丢空行（保持「一行一条事实」格式）"""
    lines = [ln.strip() for ln in str(text).replace("\r\n", "\n").split("\n")]
    return "\n".join(ln for ln in lines if ln)


@router.get("/memory")
def get_memory(request: Request):
    """读当前用户长期记忆（设置页「我的记忆」卡）"""
    uid = getattr(request.state, 'user_id', None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    from config.settings import MEMORY_MAX_ITEMS, MEMORY_MAX_CHARS
    memory = get_db().get_user_memory(uid)
    count = len([ln for ln in memory.split("\n") if ln.strip()]) if memory else 0
    return {"memory": memory, "count": count,
            "max_items": MEMORY_MAX_ITEMS, "max_chars": MEMORY_MAX_CHARS}


@router.put("/memory")
def update_memory(req: MemoryUpdate, request: Request):
    """覆盖式更新长期记忆（透明可编辑：用户可改可删任何一行）

    校验超限时拒绝而非静默截断——记忆是用户自己的数据，宁可让用户先精简。
    """
    uid = getattr(request.state, 'user_id', None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    from config.settings import MEMORY_MAX_ITEMS, MEMORY_MAX_CHARS
    normalized = _normalize_memory(req.memory)
    count = len([ln for ln in normalized.split("\n") if ln.strip()])
    if count > MEMORY_MAX_ITEMS:
        raise HTTPException(status_code=400,
                            detail=f"记忆最多 {MEMORY_MAX_ITEMS} 条，当前 {count} 条，请先精简")
    if len(normalized) > MEMORY_MAX_CHARS:
        raise HTTPException(status_code=400,
                            detail=f"记忆最多 {MEMORY_MAX_CHARS} 字，当前 {len(normalized)} 字，请先精简")
    ok = get_db().update_user_memory(uid, normalized)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True, "memory": normalized, "count": count}


class MemoryDelete(BaseModel):
    line: str = Field(..., min_length=1, max_length=200, description="要删除的记忆行（文本定位，防行号漂移）")


@router.delete("/memory")
def delete_memory_line(req: MemoryDelete, request: Request):
    """删除一条记忆（精确匹配 → 唯一子串匹配；多条命中返回 400 不误删）"""
    uid = getattr(request.state, 'user_id', None)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    r = get_db().delete_user_memory_line(uid, req.line)
    if r["total"] == 0 and r["deleted"] == 0:
        raise HTTPException(status_code=404, detail="用户不存在")
    if r["asked_more"]:
        raise HTTPException(status_code=400,
                            detail="这条内容匹配到多条记忆，请提供更完整的行内容")
    if r["deleted"] == 0:
        raise HTTPException(status_code=404, detail="记忆中没有这一条")
    count = len([ln for ln in r["memory"].split("\n") if ln.strip()]) if r["memory"] else 0
    return {"ok": True, "deleted": r["deleted"], "memory": r["memory"], "count": count}


class AgentModelUpdate(BaseModel):
    role: str       # orchestrator, analysis, collection, automation, audit
    model_id: str   # 分配给该角色的模型 ID


def _read_agent_models() -> dict:
    """读取 models.json 中的自定义 Agent 模型分配（原缺失定义，运行时 NameError 已修复）"""
    return _read_models_file().get("_agent_models", {})


@router.get("/agent-models")
def get_agent_models(request: Request):
    """获取 Agent 角色 → 模型分配（仅 5 个执行体；memory_fold/planet_article
    辅助任务键在 admin 端点管理，不暴露给用户侧）"""
    from config.settings import AGENT_MODEL_MAP, AGENT_ROLE_KEYS
    custom = _read_agent_models()
    merged = {k: AGENT_MODEL_MAP.get(k, "") for k in AGENT_ROLE_KEYS}
    merged.update({k: v for k, v in custom.items() if k in AGENT_ROLE_KEYS})
    return {"agent_models": merged}


@router.put("/agent-models")
def update_agent_models(req: AgentModelUpdate, request: Request):
    """更新 Agent 角色 → 模型分配"""
    from config.settings import AGENT_ROLE_KEYS
    valid_roles = list(AGENT_ROLE_KEYS)
    if req.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"无效角色: {req.role}，可选: {valid_roles}")
    data = _read_models_file()
    agent_models = data.get("_agent_models", {})
    agent_models[req.role] = req.model_id
    data["_agent_models"] = agent_models
    _write_models_file(data)
    # 2026-10-17 修复：用户侧写盘此前不热更新（内存 AGENT_MODEL_MAP 不变，
    # 改了分配要重启才生效）——统一补 reload
    from config.settings import reload_agent_models
    reload_agent_models()
    return {"ok": True, "role": req.role, "model_id": req.model_id}


class AgentVoiceUpdate(BaseModel):
    role: str       # orchestrator / local / analysis / collection / automation / claude
    voice_id: str   # 分配给该角色的 TTS 音色 ID（2.0 系列）


@router.get("/agent-voices")
def get_agent_voices(request: Request):
    """获取 Agent 角色 → 音色分配"""
    from config.settings import AGENT_VOICE_MAP
    custom = _read_models_file().get("_agent_voices", {})
    merged = dict(AGENT_VOICE_MAP)
    if isinstance(custom, dict):
        merged.update(custom)
    return {"agent_voices": merged}


@router.put("/agent-voices")
def update_agent_voices(req: AgentVoiceUpdate, request: Request):
    """更新 Agent 角色 → 音色分配（写入 models.json 的 _agent_voices）"""
    from config.settings import AGENT_VOICE_MAP
    valid_roles = list(AGENT_VOICE_MAP.keys())
    if req.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"无效角色: {req.role}，可选: {valid_roles}")
    data = _read_models_file()
    agent_voices = data.get("_agent_voices", {})
    if not isinstance(agent_voices, dict):
        agent_voices = {}
    agent_voices[req.role] = req.voice_id
    data["_agent_voices"] = agent_voices
    _write_models_file(data)
    # 2026-10-17 修复：音色分配此前无 reload（改完要重启才生效，用户反馈「音色
    # 不生效」的根因）——写盘后热更新内存 AGENT_VOICE_MAP
    from config.settings import reload_agent_voices
    reload_agent_voices()
    return {"ok": True, "role": req.role, "voice_id": req.voice_id}


class ApiKeyBody(BaseModel):
    provider: str
    key: str


@router.get("/apikeys")
def get_apikeys(request: Request):
    """获取已配置的 API Key（密钥脱敏，登录即可看）"""
    from api.v1.models_file import masked_apikeys
    return {"keys": masked_apikeys()}


@router.post("/apikeys")
def save_apikey(req: ApiKeyBody, request: Request):
    """保存 API Key（全局生效 → 仅 admin；否则任何登录用户可覆写全站模型密钥）"""
    from api.v1.middleware import require_admin
    require_admin(request)
    from api.v1.models_file import upsert_apikey
    upsert_apikey(req.provider, req.key)
    return {"ok": True, "provider": req.provider}


@router.delete("/apikeys")
def delete_apikey(req: ApiKeyBody, request: Request):
    """删除 API Key（仅 admin）"""
    from api.v1.middleware import require_admin
    require_admin(request)
    from api.v1.models_file import remove_apikey
    remove_apikey(req.provider)
    return {"ok": True}


class TokenCheck(BaseModel):
    token: str


@router.get("/sse-token")
def get_sse_token(request: Request):
    """签发 5 秒短期令牌（iframe 加载 HTML 资源用，替代长期 JWT 拼 URL）。

    /auth/* 是公开路径（中间件不鉴权），本端点自行校验 Authorization 头；
    sse token 由中间件 verify_sse_token 校验（单次使用 + 5 秒 TTL）。
    """
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    payload = verify_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="未登录")
    return {"token": create_sse_token(payload["user_id"], payload.get("role", "user"))}


class DeleteAccountRequest(BaseModel):
    password: str


@router.post("/delete-account")
def delete_account(req: DeleteAccountRequest, request: Request):
    """用户自助注销（C4 合规 2026-10-29，PIPL 删除权）：密码二次确认 →
    级联删除全部个人数据（会话/消息/记忆/数据集/星球/计划/日志/文件/Milvus）
    → 设备解绑。不可恢复。"""
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    payload = verify_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="未登录")
    user_id = int(payload["user_id"])
    db = get_db()
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user.get("role") == "admin":
        raise HTTPException(status_code=400, detail="管理员账号请走后台处理，不支持自助注销")
    if not db.verify_password(user_id, req.password):
        raise HTTPException(status_code=400, detail="密码错误")
    summary = db.delete_user_cascade(user_id)
    return {"ok": True, "deleted": user_id, **summary}


@router.post("/check")
def check_token(req: TokenCheck):
    """验证 token 是否有效"""
    payload = verify_token(req.token)
    if not payload:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    db = get_db()
    user = db.get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user.frozen_until and user.frozen_until > datetime.utcnow():
        return {"valid": False, "detail": "账号已被冻结"}
    if user.locked_until and user.locked_until > datetime.utcnow():
        return {"valid": False, "detail": "账号已被临时锁定"}
    return {
        "valid": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "display_name": user.display_name or user.username,
            "email": user.email or "",
            "avatar": user.avatar or "",
            "has_password": bool(user.password_hash),
            "theme": user.theme or "",
        },
    }
