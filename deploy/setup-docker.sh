#!/bin/bash
# ============================================================
# 小元AI 服务器 Docker 镜像加速一键配置（只需执行一次）
#
# 用途：国内服务器拉取 docker.io 镜像（node/nginx/mysql 等）
# 时，官方源直连不稳，需配置镜像加速。本脚本把仓库内的
# deploy/docker-daemon.json 安装到 /etc/docker/daemon.json，
# 重启 Docker 并验证拉取。
#
# 用法（服务器上，仓库根目录）：
#   bash deploy/setup-docker.sh
# ============================================================
set -e

CONF_SRC="$(cd "$(dirname "$0")" && pwd)/docker-daemon.json"
CONF_DST="/etc/docker/daemon.json"

echo "[1/4] 备份现有配置 → ${CONF_DST}.bak"
if [ -f "$CONF_DST" ]; then
  cp "$CONF_DST" "${CONF_DST}.bak"
fi

echo "[2/4] 安装镜像加速配置（xuanyuan / 1ms / daocloud 三源容错）"
mkdir -p /etc/docker
cp "$CONF_SRC" "$CONF_DST"

echo "[3/4] 重启 Docker 使配置生效"
systemctl daemon-reload
systemctl restart docker

echo "[4/4] 验证：显示生效的镜像源并测试拉取 node:18-alpine"
docker info | grep -A 3 "Registry Mirrors" || true
docker pull node:18-alpine

echo ""
echo "✅ Docker 镜像加速配置完成，可直接执行：docker compose up -d --build"
