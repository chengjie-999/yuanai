"""MySQL 数据库备份（手动/定时用）— mysqldump + gzip + 保留天数清理。

连接信息与 db/session.py 同源（utils.sensitive_data.get_mysql_config，.env 里的 MySQL 配置）。

用法：
    python scripts/backup_db.py                 # 备份到 backups/，保留 14 天
    python scripts/backup_db.py --keep 30       # 保留 30 天
    python scripts/backup_db.py --out /mnt/bak  # 指定备份目录

服务器上（Docker 部署）推荐直接用 docker-compose 里的 backup 服务（每天自动备份，
本脚本供手动备份/本机备份使用）。
"""
import argparse
import gzip
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.data_path import root_path  # noqa: E402


def _mysql_config() -> dict:
    try:
        from utils.sensitive_data import get_mysql_config
        cfg = get_mysql_config()
        if cfg and cfg.get("host"):
            return cfg
    except Exception:
        pass
    # 环境变量兜底（Docker 部署约定）
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": os.getenv("MYSQL_PORT", "3306"),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "ai_agent"),
    }


def main():
    parser = argparse.ArgumentParser(description="MySQL 备份")
    parser.add_argument("--keep", type=int, default=14, help="保留天数（默认 14）")
    parser.add_argument("--out", default="", help="备份目录（默认 <项目>/backups）")
    args = parser.parse_args()

    cfg = _mysql_config()
    out_dir = args.out or os.path.join(root_path(), "backups")
    os.makedirs(out_dir, exist_ok=True)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = os.path.join(out_dir, f"{cfg['database']}_{stamp}.sql.gz")

    # mysqldump 输出直接管道进 gzip，避免落盘完整明文
    dump = subprocess.Popen(
        ["mysqldump", "-h", cfg["host"], "-P", str(cfg.get("port", 3306)),
         "-u", cfg["user"], f"-p{cfg['password']}",
         "--single-transaction", "--quick", "--set-gtid-purged=OFF",
         cfg["database"]],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    with gzip.open(target, "wb") as f:
        shutil.copyfileobj(dump.stdout, f)
    err = dump.stderr.read().decode(errors="replace")
    if dump.wait() != 0:
        os.remove(target)
        print(f"❌ mysqldump 失败: {err[:500]}")
        sys.exit(1)
    size_kb = os.path.getsize(target) / 1024
    print(f"✅ 备份完成: {target}（{size_kb:.0f} KB）")

    # 清理 keep 天之前的备份
    cutoff = time.time() - args.keep * 86400
    removed = 0
    for f in os.listdir(out_dir):
        if not f.endswith(".sql.gz"):
            continue
        fp = os.path.join(out_dir, f)
        if os.path.getmtime(fp) < cutoff:
            os.remove(fp)
            removed += 1
    if removed:
        print(f"🧹 清理过期备份 {removed} 个（保留 {args.keep} 天）")


if __name__ == "__main__":
    main()
