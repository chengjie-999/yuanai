"""data/models.json 读写单点（auth 与 admin 共用，消除双份实现）

models.json 结构：{模型id: {label, provider}, "_agent_models": {...}, "_agent_voices": {...}, "_apikeys": {...}}

S3.1：_apikeys 值透明加解密（读写单点实现，6 处调用方零改动）：
- 写：ENCRYPTION_PASSWORD 存在时自动加密为 {"encrypted_data":..., "salt":...}；
  未设置则明文写入并告警（生产必须配置）
- 读：密文 dict 自动解密为明文；旧明文兼容（并告警提示下次写入自动迁移）
- 原子写（tmp + os.replace）
- 强约束：ENCRYPTION_PASSWORD 轮换前必须先 `python -m api.v1.models_file --decrypt-to-plain`
  （旧密码解出明文）→ 换密码 → `python -m api.v1.models_file --migrate`（新密码加密），
  否则密文永久不可解
"""

import json
import logging
import os
import sys

from utils.data_path import root_path

logger = logging.getLogger(__name__)

_MODELS_PATH = os.path.join(root_path(), "data", "models.json")


def _pwd() -> str:
    return os.getenv("ENCRYPTION_PASSWORD", "")


def read_models_file() -> dict:
    """读 models.json；_apikeys 密文值自动解密为明文（调用方无感知）"""
    data = {}
    if os.path.exists(_MODELS_PATH):
        with open(_MODELS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    keys = data.get("_apikeys")
    if isinstance(keys, dict):
        from utils.sensitive_data import decrypt_sensitive_data

        out = {}
        for provider, value in keys.items():
            if isinstance(value, dict) and "encrypted_data" in value:
                if not _pwd():
                    raise RuntimeError("未设置 ENCRYPTION_PASSWORD，无法解密 _apikeys 密文")
                out[provider] = decrypt_sensitive_data(value, _pwd())
            else:
                out[provider] = value
                if value:
                    logger.warning("models.json 存在明文 API Key（%s），下次写入将自动加密", provider)
        data["_apikeys"] = out
    return data


def write_models_file(data: dict):
    """写 models.json；_apikeys 明文在 ENCRYPTION_PASSWORD 存在时自动加密"""
    d = dict(data)
    keys = d.get("_apikeys")
    if isinstance(keys, dict):
        from utils.sensitive_data import encrypt_sensitive_data

        if _pwd():
            d["_apikeys"] = {
                p: (encrypt_sensitive_data(v, _pwd()) if isinstance(v, str) else v)
                for p, v in keys.items()
            }
        elif keys:
            logger.warning("未设置 ENCRYPTION_PASSWORD，_apikeys 以明文写入（生产必须配置）")
    os.makedirs(os.path.dirname(_MODELS_PATH), exist_ok=True)
    tmp = _MODELS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _MODELS_PATH)


# ---- API Key 端点共享逻辑（2026-10-21 清洁5：auth 与 admin 双实现合一；
# admin GET 原样返回明文 key，一并收口为脱敏） ----

def masked_apikeys() -> dict:
    """API Key 脱敏列表（provider → xxxx****xxxx）"""
    keys = read_models_file().get("_apikeys", {})
    return {k: v[:4] + "****" + v[-4:] if len(v) > 8 else "****"
            for k, v in keys.items() if isinstance(v, str)}


def upsert_apikey(provider: str, key: str) -> None:
    data = read_models_file()
    keys = data.get("_apikeys", {})
    keys[provider] = key
    data["_apikeys"] = keys
    write_models_file(data)


def remove_apikey(provider: str) -> None:
    data = read_models_file()
    keys = data.get("_apikeys", {})
    keys.pop(provider, None)
    if keys:
        data["_apikeys"] = keys
    else:
        data.pop("_apikeys", None)
    write_models_file(data)


def _migrate(action: str) -> None:
    """一次性迁移 CLI：--migrate（当前密码加密）/ --decrypt-to-plain（当前密码解出明文）

    注意 decrypt-to-plain 必须绕过 write_models_file 直接落盘——
    否则刚解出的明文会被透明加密再次写回。
    """
    if not os.path.exists(_MODELS_PATH):
        print(f"{_MODELS_PATH} 不存在，无需迁移")
        return
    raw = json.load(open(_MODELS_PATH, "r", encoding="utf-8"))
    keys = raw.get("_apikeys") or {}
    if not keys:
        print("_apikeys 为空，无需迁移")
        return
    if action == "decrypt-to-plain":
        from utils.sensitive_data import decrypt_sensitive_data
        for p, v in keys.items():
            if isinstance(v, dict) and "encrypted_data" in v:
                if not _pwd():
                    raise RuntimeError("未设置 ENCRYPTION_PASSWORD（需旧密码）")
                keys[p] = decrypt_sensitive_data(v, _pwd())
        raw["_apikeys"] = keys
        # 直接原子落盘明文（不能走 write_models_file——会被再加密）
        os.makedirs(os.path.dirname(_MODELS_PATH), exist_ok=True)
        tmp = _MODELS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _MODELS_PATH)
        print(f"迁移完成（decrypt-to-plain）：{len(keys)} 个 key 已解密为明文")
        return
    if action == "migrate":
        from utils.sensitive_data import encrypt_sensitive_data
        if not _pwd():
            raise RuntimeError("未设置 ENCRYPTION_PASSWORD（需新密码）")
        for p, v in keys.items():
            if isinstance(v, str):
                keys[p] = encrypt_sensitive_data(v, _pwd())
    raw["_apikeys"] = keys
    write_models_file(raw)
    # 回读断言：明文条目读回应一致；密文条目（未动）至少能解出明文
    back = read_models_file().get("_apikeys", {})
    for p, v in keys.items():
        if isinstance(v, str) and back.get(p) != v:
            raise RuntimeError(f"迁移回读不一致: {p}")
        if isinstance(v, dict) and p not in back:
            raise RuntimeError(f"密文条目解密失败: {p}")
    print(f"迁移完成（{action}）：{len(keys)} 个 key 已处理")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "migrate"
    _migrate(action)
