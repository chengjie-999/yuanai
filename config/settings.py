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
DEFAULT_MODEL = "doubao-seed-2-0-pro-260215"
DEFAULT_TEMPERATURE = 0.7

# ===================== 鉴权配置 =====================

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", os.urandom(32).hex())
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
    "host": "localhost",
    "port": 6379,
    "db": 0,
}

# ===================== 系统配置 =====================

CHAT_TOOLS_ADMIN_SKIP = {"scroll", "click", "zoom", "restore", "question", "task",
                         "home", "html", "mark_", "submit", "confirm", "page_status",
                         "save_cookie", "load_cookie", "save_page_cookies", "load_page_cookies"}

CHAT_TOOLS_USER_SKIP = CHAT_TOOLS_ADMIN_SKIP | {"browser", "launch", "open_", "website",
                                                  "cookie", "refresh"}
