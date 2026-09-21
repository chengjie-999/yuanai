#!/bin/sh
# 数据库自动备份容器入口（docker-compose 的 backup 服务）
# 启动即备份一次，此后每 BACKUP_INTERVAL_HOURS（默认 24）小时一次；保留 BACKUP_KEEP_DAYS 天
set -e

mkdir -p /backups
echo "[backup] 启动，间隔 ${BACKUP_INTERVAL_HOURS:-24}h，保留 ${BACKUP_KEEP_DAYS:-14} 天"

while true; do
  STAMP=$(date +%Y%m%d_%H%M%S)
  DB="${MYSQL_DATABASE:-ai_agent}"
  if mysqldump -h "$MYSQL_HOST" -u root -p"$MYSQL_PASSWORD" \
       --single-transaction --quick --set-gtid-purged=OFF "$DB" 2>/tmp/dump.err \
       | gzip > "/backups/${DB}_${STAMP}.sql.gz"; then
    echo "[backup] ✅ ${DB}_${STAMP}.sql.gz"
  else
    echo "[backup] ❌ 备份失败: $(head -c 300 /tmp/dump.err)"
  fi

  # 清理过期备份
  find /backups -name '*.sql.gz' -mtime +"${BACKUP_KEEP_DAYS:-14}" -delete

  sleep "${BACKUP_INTERVAL_HOURS:-24}h"
done
