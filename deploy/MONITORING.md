# 服务器监控告警方案（部署建议）

## 现状

- 应用层已有：`/health` 健康端点（backend/frontend 容器都有 healthcheck，docker 自动重启异常容器）
- 缺失：资源级监控（CPU/内存/磁盘/带宽）与外部探活告警

## 推荐方案（火山引擎生态，零自建成本）

### 1. 云监控基础告警（免费）

火山引擎控制台 → 云监控（CloudMonitor）→ 告警规则，对 ECS 实例配置：

| 指标 | 阈值建议 | 说明 |
|------|---------|------|
| CPU 使用率 | > 85% 持续 5 分钟 | 异常进程/爬虫并发 |
| 内存使用率 | > 85% 持续 5 分钟 | Milvus/Chrome 内存大户 |
| 磁盘使用率 | > 80% | `/var/lib/docker` 增长（图片/备份） |
| 公网出带宽 | > 80% 持续 10 分钟 | 大文件分发/异常流量 |

通知方式：短信（免费额度内）/ 邮件。

### 2. 外部探活（可选，Uptime Kuma / 云拨测）

- 探测 `https://cjyuanai.cn/health`（每 1-5 分钟，失败 3 次告警）
- 火山引擎「云拨测」有免费额度，或服务器上跑 Uptime Kuma（探测别处站点，互相探活更可靠）

### 3. 日志兜底

- `docker compose logs --tail 200 backend` 日常排查
- 可选：`docker logs --since 24h spider-backend 2>&1 | grep -i error` 每日巡检脚本

## 数据库备份（已内置）

- `docker-compose.yml` 的 `backup` 服务：每天自动 mysqldump 到 `backup_data` 卷，保留 14 天
- 手动备份：服务器上 `docker exec spider-backend python scripts/backup_db.py`
- 备份文件拉回本地：`docker cp spider-backup:/backups/xxx.sql.gz .`
- **异地**：每月把最新备份下载到本地/对象存储（单机备份防不了磁盘损坏）

## 部署步骤（一次性）

1. `docker compose up -d`（backup 服务随其他服务一起拉起）
2. 火山控制台配置云监控告警规则（上表）
3. 收到第一条测试告警后确认通知渠道正常
