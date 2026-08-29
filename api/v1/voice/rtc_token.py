"""火山引擎 RTC Token 生成（纯 Python，零第三方依赖）

VeRTC 鉴权 Token 为 JWT 风格三字段结构，签名算法 HMAC-SHA256，密钥为 RTC 应用 AppKey：

    base64url(header) + "." + base64url(payload) + "." + base64url(signature)

- header 固定 {"alg": "HMAC-SHA256", "type": "JWT"}
- payload 包含 app_id / room_id / user_id / privileges（publish、subscribe 为各自过期时间戳）
  / expire_at / nonce
- signature = HMAC-SHA256(前两段拼接串, AppKey) 的原始字节再 base64url

进房时 roomID / userID 必须与生成 Token 时一致；base64url 不带 padding。
参考火山引擎官方 RTC 鉴权文档（docs/6348 系列）与官方多语言示例。
"""

import base64
import hashlib
import hmac
import json
import time
import uuid


def _b64url(data: bytes) -> str:
    """base64url 编码，去掉 padding（Token 协议约定）"""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_json(obj: dict) -> str:
    return _b64url(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def generate_rtc_token(
    app_id: str,
    app_key: str,
    room_id: str,
    user_id: str,
    expire_seconds: int = 24 * 3600,
) -> str:
    """生成进房 Token（publish + subscribe 双权限，默认 24 小时有效）"""
    now = int(time.time())
    expire_at = now + expire_seconds
    header = {"alg": "HMAC-SHA256", "typ": "JWT"}
    payload = {
        "app_id": app_id,
        "room_id": room_id,
        "user_id": user_id,
        "privileges": {
            "publish": expire_at,
            "subscribe": expire_at,
        },
        "expire_at": expire_at,
        "nonce": uuid.uuid4().hex,
    }
    content = f"{_b64url_json(header)}.{_b64url_json(payload)}"
    signature = hmac.new(app_key.encode("utf-8"), content.encode("utf-8"), hashlib.sha256).digest()
    return f"{content}.{_b64url(signature)}"
