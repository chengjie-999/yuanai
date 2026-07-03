import os
from dotenv import load_dotenv

load_dotenv()

# ===================== 模型配置 =====================

import json as _json
from pathlib import Path as _Path

_DEFAULT_MODELS = {
    "doubao-seed-2-0-pro-260215": {"label": "豆包 Pro", "provider": "Doubao"},
    "doubao-seed-2-0-lite-260215": {"label": "豆包 Lite", "provider": "Doubao"},
    "deepseek-v4-flash": {"label": "DeepSeek V4 Flash", "provider": "DeepSeek"},
    "deepseek-v4-pro": {"label": "DeepSeek V4 Pro", "provider": "DeepSeek"},
}

def _load_models() -> dict:
    models = dict(_DEFAULT_MODELS)
    try:
        custom_path = _Path(__file__).parent.parent / "data" / "models.json"
        if custom_path.exists():
            with open(custom_path, "r", encoding="utf-8") as f:
                custom = _json.load(f)
            if isinstance(custom, dict):
                models.update(custom)
    except Exception:
        pass
    return models

MODELS = _load_models()

MODEL_NAMES = list(MODELS.keys())
DEFAULT_MODEL = "deepseek-v4-flash"
VISION_MODEL = "doubao-seed-2-0-pro-260215"  # DeepSeek V4 不支持图片，识图自动切豆包
DEFAULT_TEMPERATURE = 0.7

# Agent 模型分配 — 统一入口，消除代码中 15+ 处硬编码
AGENT_MODEL_MAP = {
    "orchestrator": "doubao-seed-2-0-lite-260215",
    "analysis": "doubao-seed-2-0-pro-260215",
    "collection": "doubao-seed-2-0-lite-260215",
    "automation": "doubao-seed-2-0-pro-260215",
    "audit": "doubao-seed-2-0-pro-260215",
}

# ===================== 鉴权配置 =====================

_jwt = os.getenv("JWT_SECRET_KEY")
if not _jwt or _jwt == "change-me-to-a-random-secret":
    if os.getenv("APP_ENV") == "production":
        raise RuntimeError("JWT_SECRET_KEY 未设置，生产环境必须设置此环境变量")
    # 持久化到文件，避免重启后 token 全部失效
    _secret_file = _Path(__file__).parent / ".jwt_secret"
    if _secret_file.exists():
        _jwt = _secret_file.read_text(encoding="utf-8").strip()
    else:
        _jwt = os.urandom(32).hex()
        _secret_file.write_text(_jwt, encoding="utf-8")
JWT_SECRET_KEY = _jwt
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7

# ===================== 数据库配置 =====================

MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "database": "ai_agent",
}

REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", "6379")),
    "db": int(os.getenv("REDIS_DB", "0")),
}

# ===================== 系统配置 =====================

# ===================== 云数据库配置 =====================

CLOUD_MYSQL_CONFIG = {
    "host": os.getenv("CLOUD_MYSQL_HOST", ""),
    "port": int(os.getenv("CLOUD_MYSQL_PORT", "3306")),
    "user": os.getenv("CLOUD_MYSQL_USER", "root"),
    "database": os.getenv("CLOUD_MYSQL_DATABASE", "ai_agent"),
}

# ===================== 火山引擎 TOS 配置 =====================

TOS_CONFIG = {
    "access_key_id": os.getenv("TOS_ACCESS_KEY_ID", ""),
    "access_key_secret": os.getenv("TOS_ACCESS_KEY_SECRET", ""),
    "endpoint": os.getenv("TOS_ENDPOINT", ""),
    "bucket": os.getenv("TOS_BUCKET", ""),
    "region": os.getenv("TOS_REGION", ""),
}

# ===================== 备份配置 =====================

BACKUP_DIR = os.getenv("BACKUP_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "backups"))
BACKUP_RETENTION_COUNT = int(os.getenv("BACKUP_RETENTION_COUNT", "4"))
