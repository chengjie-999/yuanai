"""火山引擎 VeRTC Token 生成（纯 Python，零第三方依赖）

格式依据官方 rtc-aigc-demo（Server/token.js）+ 控制台临时 Token 实测反推验证：

    token = "001" + AppID + base64(content)
    content = [u16 msgLen][msg][u16 sigLen][sig]        （全部小端）
    msg = [u32 nonce][u32 issuedAt][u32 expireAt]
          [u16 roomLen][room][u16 userLen][user]
          [u16 privCount][(u16 privKey, u32 expire)]...
    sig = HMAC-SHA256(AppKey, msg) 的 32 字节原始摘要
    base64 为标准 base64（含 padding，非 urlsafe）

privileges 键（与控制台临时 Token 一致）：
    0 = PrivPublishStream（发布流）
    1 = 发布音频流   2 = 发布视频流   3 = 发布数据流
    4 = PrivSubscribeStream（订阅流）   5 = 订阅数据流
进房 roomID/userID 必须与生成 Token 时一致。
"""

import base64
import hashlib
import hmac
import random
import struct
import time


def _pack_str(data: bytes) -> bytes:
    return struct.pack("<H", len(data)) + data


def _build_msg(app_id: str, room_id: str, user_id: str, expire_at: int, issued_at: int, nonce: int) -> bytes:
    """构造待签名的 msg 二进制（所有整数小端）"""
    # 与控制台临时 Token 相同的 6 项权限（发布流/音/视/数据 + 订阅流/数据）
    privileges = {0: expire_at, 1: expire_at, 2: expire_at, 3: expire_at, 4: expire_at, 5: expire_at}
    buf = struct.pack("<III", nonce, issued_at, expire_at)
    buf += _pack_str(room_id.encode("utf-8"))
    buf += _pack_str(user_id.encode("utf-8"))
    buf += struct.pack("<H", len(privileges))
    for key, expire in privileges.items():
        buf += struct.pack("<HI", key, expire)
    return buf


def generate_rtc_token(
    app_id: str,
    app_key: str,
    room_id: str,
    user_id: str,
    expire_seconds: int = 24 * 3600,
) -> str:
    """生成进房 Token（"001" 新版格式，默认 24 小时有效）"""
    now = int(time.time())
    msg = _build_msg(app_id, room_id, user_id, now + expire_seconds, now, random.getrandbits(32))
    signature = hmac.new(app_key.encode("utf-8"), msg, hashlib.sha256).digest()
    content = _pack_str(msg) + _pack_str(signature)
    return "001" + app_id + base64.b64encode(content).decode("ascii")
