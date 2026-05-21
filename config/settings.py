import os
from dotenv import load_dotenv

load_dotenv()

# ===================== 模型配置 =====================

MODELS = {
    "doubao-seed-2-0-pro-260215": {"label": "豆包 Pro", "provider": "Doubao"},
    "doubao-seed-2-0-lite-260215": {"label": "豆包 Lite", "provider": "Doubao"},
    "deepseek-v4-flash": {"label": "DeepSeek V4 Flash", "provider": "DeepSeek"},
    "deepseek-v4-pro": {"label": "DeepSeek V4 Pro", "provider": "DeepSeek"},
}

MODEL_NAMES = list(MODELS.keys())
DEFAULT_MODEL = "deepseek-v4-flash"
VISION_MODEL = "doubao-seed-2-0-pro-260215"  # DeepSeek V4 不支持图片，识图自动切豆包
DEFAULT_TEMPERATURE = 0.7

# ===================== 鉴权配置 =====================

_jwt = os.getenv("JWT_SECRET_KEY")
if not _jwt or _jwt == "change-me-to-a-random-secret":
    if os.getenv("APP_ENV") == "production":
        raise RuntimeError("JWT_SECRET_KEY 未设置，生产环境必须设置此环境变量")
    _jwt = os.urandom(32).hex()
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
