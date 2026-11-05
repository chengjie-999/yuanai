# -*- coding: utf-8 -*-
"""邮箱验证码登录（R1'，2026-11-05）——注册登录合一，零资质先行通道。

短信通道（火山 SMS）资质到位后同构并轨（同款验证码逻辑，仅发送介质不同）。

防刷护栏（与功能同日上线，不可裸奔）：
- 同邮箱 60s 冷却（Redis TTL）
- 每邮箱每日 10 条（Redis 日配额，复用 quota 基建）
- 验证码错 5 次作废（需重新发码）
- 验证码 Redis 存 5 分钟（TTL），恒定时间比对
- 发送接口本身受全局 API 限流（60 次/60s/IP）
"""
import hashlib
import hmac
import logging
import secrets
import smtplib
import time
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText

from db.session import get_db
from api.v1.auth.utils import create_token, verify_token, register_login_session

logger = logging.getLogger(__name__)

CODE_TTL = 300          # 验证码有效期 5 分钟
COOLDOWN = 60           # 同邮箱发送冷却 60s
DAILY_SEND_LIMIT = 10   # 每邮箱每日发送上限
MAX_TRY = 5             # 错误次数上限（超限作废）

_CODE_KEY = "emailcode:{email}"
_CD_KEY = "emailcode:cd:{email}"
_TRY_KEY = "emailcode:try:{email}"


def smtp_configured() -> bool:
    """SMTP 是否完整配置（env 或后台热配置；未配置时发送端点 503）"""
    from config.settings import EMAIL_LOGIN_ENABLED, get_smtp_config
    cfg = get_smtp_config()
    return bool(EMAIL_LOGIN_ENABLED and cfg["host"] and cfg["port"]
                and cfg["user"] and cfg["password"])


def _rds():
    """Redis 客户端（测试可 monkeypatch 为内存 stub）"""
    from db.redis_client import get_redis
    return get_redis()


def _gen_code() -> str:
    return str(secrets.randbelow(10 ** 6)).zfill(6)


def _send_email(to: str, code: str, subject: str = "【小元AI】邮箱验证码",
                body_plain: str = "", body_html: str = "") -> None:
    """SMTP 发送邮件（同步阻塞，调用方放线程池）。失败抛异常。

    multipart/alternative：纯文本兜底 + HTML 品牌版（验证码大字高亮——
    2026-11-06 用户拍板「验证码不够显著」）。
    """
    from config.settings import get_smtp_config
    cfg = get_smtp_config()
    if not body_plain:
        body_plain = (f"您好！\n\n您的验证码是：{code}\n"
                      f"验证码 5 分钟内有效，请勿泄露给他人。\n\n"
                      "如果不是您本人操作，请忽略本邮件。\n\n—— 小元AI")
        body_html = _code_email_html(code)
    from email.mime.multipart import MIMEMultipart
    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    # 发件人：支持「显示名 <地址>」形态（中文显示名经 Header 编码，
    # 否则非 ASCII 头直接发会 UnicodeEncodeError）
    from email.utils import parseaddr, formataddr
    _display, _addr = parseaddr(cfg["from_addr"] or cfg["user"])
    if _display:
        msg["From"] = formataddr((str(Header(_display, "utf-8")), _addr))
    else:
        msg["From"] = _addr or cfg["user"]
    msg["To"] = to
    msg.attach(MIMEText(body_plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    if cfg["use_ssl"]:
        server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=15)
    else:
        server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=15)
        server.starttls()
    try:
        server.login(cfg["user"], cfg["password"])
        server.sendmail(cfg["user"], [to], msg.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass


def _code_email_html(code: str) -> str:
    """验证码邮件 HTML：大字验证码居中高亮（品牌蓝），5 分钟有效 + 防泄露提示"""
    return f"""\
<div style="max-width:480px;margin:0 auto;font-family:'PingFang SC','Microsoft YaHei',sans-serif;
            background:#f8fafc;border-radius:12px;padding:32px 28px;text-align:center;">
  <div style="font-size:18px;font-weight:700;color:#0f172a;margin-bottom:4px;">小元AI</div>
  <div style="font-size:13px;color:#64748b;margin-bottom:24px;">邮箱验证码</div>
  <div style="font-size:14px;color:#334155;margin-bottom:16px;">您好！您的验证码是</div>
  <div style="font-size:34px;font-weight:800;letter-spacing:10px;color:#2563eb;
              background:#ffffff;border:1px solid #cbd5e1;border-radius:10px;
              padding:18px 12px;margin-bottom:16px;">{code}</div>
  <div style="font-size:12.5px;color:#64748b;line-height:1.8;">
    验证码 5 分钟内有效，请勿泄露给他人。<br/>
    如果不是您本人操作，请忽略本邮件。
  </div>
  <div style="margin-top:24px;padding-top:16px;border-top:1px solid #e2e8f0;
              font-size:12px;color:#94a3b8;">—— 小元AI</div>
</div>"""


def send_test_email(to: str) -> None:
    """后台「发送测试邮件」：验证配置连通性（失败抛异常，端点转 502）"""
    _send_email(to, "000000",
                subject="【小元AI】邮件配置测试",
                body_plain="您好！\n\n这是一封测试邮件——收到即表示邮箱验证码登录功能配置成功。\n\n—— 小元AI",
                body_html="""\
<div style="max-width:480px;margin:0 auto;font-family:'PingFang SC','Microsoft YaHei',sans-serif;
            background:#f8fafc;border-radius:12px;padding:32px 28px;text-align:center;">
  <div style="font-size:18px;font-weight:700;color:#0f172a;">小元AI</div>
  <div style="font-size:14px;color:#334155;margin:16px 0;">
    这是一封测试邮件——收到即表示邮箱验证码登录功能配置成功。
  </div>
  <div style="margin-top:24px;padding-top:16px;border-top:1px solid #e2e8f0;
              font-size:12px;color:#94a3b8;">—— 小元AI</div>
</div>""")


async def send_email_code(email: str) -> dict:
    """发送验证码（已过冷却/限额检查）。返回 {cooldown} 秒数。"""
    import asyncio
    rds = _rds()
    code = _gen_code()
    rds.set(_CODE_KEY.format(email=email), code, ex=CODE_TTL)
    rds.set(_TRY_KEY.format(email=email), 0, ex=CODE_TTL)
    await asyncio.to_thread(_send_email, email, code)
    rds.set(_CD_KEY.format(email=email), 1, ex=COOLDOWN)
    return {"cooldown": COOLDOWN}


def check_cooldown(email: str) -> int:
    """返回剩余冷却秒数（0 = 可发送）。Redis 故障降级放行。"""
    try:
        rds = _rds()
        if rds.get(_CD_KEY.format(email=email)):
            return max(0, int(rds.ttl(_CD_KEY.format(email=email)) or 1))
    except Exception:
        pass
    return 0


def verify_email_code(email: str, code: str) -> bool:
    """验证码校验：恒定时间比对 + 错 5 次作废。True=通过。"""
    rds = _rds()
    try_count = 0
    try:
        try_count = int(rds.get(_TRY_KEY.format(email=email)) or 0)
    except Exception:
        pass
    stored = rds.get(_CODE_KEY.format(email=email))
    if not stored or try_count >= MAX_TRY:
        return False
    if not hmac.compare_digest(str(stored), str(code)):
        # 错误次数 +1（与验证码同 TTL）；达到上限即作废
        new_try = try_count + 1
        rds.set(_TRY_KEY.format(email=email), new_try, ex=CODE_TTL)
        if new_try >= MAX_TRY:
            rds.delete(_CODE_KEY.format(email=email))
        return False
    # 验证通过：一次性消费（防重放）
    rds.delete(_CODE_KEY.format(email=email))
    rds.delete(_TRY_KEY.format(email=email))
    return True


def consume_send_quota(email: str, limit: int = DAILY_SEND_LIMIT) -> bool:
    """每日发送配额消耗（Redis 日配额，失败降级放行）。"""
    from api.v1.db_helpers import consume_daily_quota
    return consume_daily_quota(f"emailcode:{email}", limit)


def _gen_username(email: str) -> str:
    """自动分配用户名：确定性生成（同邮箱反复请求同结果，幂等）"""
    h = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    return f"u_{h[:10]}"


def _gen_display_name(email: str) -> str:
    """自动分配昵称：小元用户_xxxx"""
    h = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    return f"小元用户_{h[:4]}"


def _token_for(user) -> str:
    """签发令牌 + 登录会话登记（与 /auth/login 同口径，含 5 台设备限制）"""
    token = create_token(user.id, user.role, user.username, track_session=True)
    _pl = verify_token(token) or {}
    _exp = _pl.get("exp")
    exp_ts = _exp if isinstance(_exp, (int, float)) else (
        _exp.timestamp() if hasattr(_exp, "timestamp") else time.time() + 86400)
    register_login_session(user.id, _pl.get("jti", ""), exp_ts)
    return token


def email_login(email: str, code: str, agreement_accepted: bool = False) -> dict:
    """验证码登录（注册登录合一）：
    用户存在 → 直接登录；不存在 → 自动注册（协议勾选强制留痕）→ 自动登录。
    返回 {"token", "user_id", "username", "is_new", ...} 或 {"error", ...}。"""
    if not verify_email_code(email, code):
        return {"error": "验证码错误或已失效"}

    from db.session import User
    db = get_db()
    with db.session() as sess:
        user = sess.query(User).filter_by(email=email.strip().lower()).first()
        if user is None:
            # 自动注册：协议勾选后端强制（未勾选 422），注册即留痕 agreed_at
            if not agreement_accepted:
                return {"error": "请先阅读并同意《用户协议》与《隐私政策》", "agreement_required": True}
            username = _gen_username(email)
            # 唯一性兜底：撞库概率极低，重名时换后缀
            if sess.query(User).filter_by(username=username).first():
                username = f"{username}_{secrets.token_hex(2)}"
            password = secrets.token_urlsafe(16)  # 随机密码：验证码即登录方式，用户不可见
            import bcrypt as _bcrypt
            user = User(username=username, email=email.strip().lower(),
                        password_hash=_bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode(),
                        display_name=_gen_display_name(email),
                        role="user", agreed_at=datetime.utcnow())
            sess.add(user)
            sess.commit()
            sess.refresh(user)
            is_new = True
            logger.info("邮箱验证码自动注册: username=%s email=%s", username, email)
        else:
            is_new = False
            if not user.agreed_at:
                user.agreed_at = datetime.utcnow()
                sess.commit()

    # 冻结检查（C7）：与密码登录同口径
    if user.frozen_until and user.frozen_until > datetime.utcnow():
        days = (user.frozen_until - datetime.utcnow()).days
        reason = (user.freeze_reason or "").strip()
        detail = f"账号已被冻结，剩余 {days} 天"
        if reason:
            detail += f"。冻结原因：{reason}"
        detail += "。如有异议可通过申诉入口提交申诉。"
        return {"error": detail, "frozen": True}

    db.reset_login_attempts(user.id)
    logger.info("邮箱验证码登录成功: user=%s email=%s is_new=%s",
                user.username, email, is_new)
    return {"token": _token_for(user), "user_id": user.id, "username": user.username,
            "display_name": user.display_name or user.username, "is_new": is_new}
