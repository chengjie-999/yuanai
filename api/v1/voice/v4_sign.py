"""火山引擎 OpenAPI V4 签名（纯 Python，零第三方依赖）

用于调用 RTC OpenAPI（StartVoiceChat / StopVoiceChat，域 rtc.volcengineapi.com）。

签名流程（参考火山引擎通用签名机制与官方 veadk 实现）：
1. CanonicalRequest = HTTPMethod\n URI\n CanonicalQueryString\n CanonicalHeaders\n SignedHeaders\n HexSha256(Payload)
2. StringToSign = HMAC-SHA256\n {X-Date}\n {CredentialScope}\n HexSha256(CanonicalRequest)
3. SigningKey = HMAC(HMAC(HMAC(HMAC(SecretKey, Date), Region), Service), "request")
4. Signature = Hex(HMAC(SigningKey, StringToSign))
5. Authorization: HMAC-SHA256 Credential={AK}/{CredentialScope}, SignedHeaders={...}, Signature={...}
"""

import hashlib
import hmac
from urllib.parse import quote


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _hex_sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _canonical_query(params: dict) -> str:
    """按 key 排序并 URL 编码（RFC 3986 风格，空格编码为 %20）"""
    def enc(s: str) -> str:
        return quote(str(s), safe="-_.~")
    return "&".join(f"{enc(k)}={enc(v)}" for k, v in sorted(params.items()))


def v4_sign_request(
    access_key: str,
    secret_key: str,
    method: str,
    host: str,
    uri: str,
    query: dict,
    payload: str,
    region: str = "cn-north-1",
    service: str = "rtc",
    x_date: str = None,
) -> dict:
    """生成 V4 签名请求头。返回完整 headers dict（含 Authorization 与 X-* 头）。

    x_date 格式 YYYYMMDDTHHMMSSZ（UTC），不传则取当前 UTC 时间。
    """
    from datetime import datetime, timezone
    if x_date is None:
        x_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    date = x_date[:8]  # YYYYMMDD

    canonical_query = _canonical_query(query)
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical_headers = (
        f"content-type:application/json\n"
        f"host:{host}\n"
        f"x-content-sha256:{_hex_sha256(payload)}\n"
        f"x-date:{x_date}\n"
    )
    canonical_request = "\n".join([
        method,
        uri,
        canonical_query,
        canonical_headers,
        signed_headers,
        _hex_sha256(payload),
    ])

    credential_scope = f"{date}/{region}/{service}/request"
    string_to_sign = "\n".join([
        "HMAC-SHA256",
        x_date,
        credential_scope,
        _hex_sha256(canonical_request),
    ])

    k_date = _hmac_sha256(secret_key.encode("utf-8"), date)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    k_signing = _hmac_sha256(k_service, "request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "Content-Type": "application/json",
        "Host": host,
        "X-Date": x_date,
        "X-Content-Sha256": _hex_sha256(payload),
        "Authorization": authorization,
    }
