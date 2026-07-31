"""
Alembic 迁移环境配置 — 小元AI

用法：
  alembic revision --autogenerate -m "描述"   # 自动检测模型变更，生成迁移
  alembic upgrade head                          # 应用到最新版本
  alembic downgrade -1                          # 回滚一个版本
  alembic current                               # 查看当前版本
  alembic history                               # 查看迁移历史
"""

import sys
import os
import logging
from urllib.parse import quote_plus

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import engine_from_config, pool
from alembic import context

# Alembic Config 对象
config = context.config

# 日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("alembic")

# ---------------------- 目标元数据 ----------------------
# 从 db/session.py 导入所有 ORM 模型（Base.metadata 包含全部表）
from db.session import Base
target_metadata = Base.metadata


def get_db_url() -> str:
    """从项目配置获取数据库连接 URL（手动编码密码，处理 @ 等特殊字符）"""
    from utils.sensitive_data import get_mysql_config
    cfg = get_mysql_config()
    user = cfg.get("user", "root")
    password = quote_plus(cfg.get("password", ""))
    host = cfg.get("host", "localhost")
    port = cfg.get("port", 3306)
    database = cfg.get("database", "ai_agent")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本（不连接数据库）"""
    url = get_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库并执行迁移"""
    connectable = engine_from_config(
        {"sqlalchemy.url": get_db_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
