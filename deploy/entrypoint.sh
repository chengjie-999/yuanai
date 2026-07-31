#!/bin/bash
set -e

echo "=== 等待 MySQL 就绪 ==="
until python -c "import pymysql; pymysql.connect(host='$MYSQL_HOST', port=int('${MYSQL_PORT:-3306}'), user='$MYSQL_USER', password='$MYSQL_PASSWORD', database='$MYSQL_DATABASE')" 2>/dev/null; do
    echo "  等待 MySQL..."
    sleep 2
done
echo "  MySQL 已连接"

echo "=== 初始化数据库表 ==="
python -c "
from db.session import get_db
db = get_db()
print('  数据库表已就绪')
"

echo "=== 应用数据库迁移 ==="
alembic upgrade head
echo "  迁移已完成"

echo "=== 启动 API 服务 ==="
exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1
