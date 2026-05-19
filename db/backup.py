"""数据库备份 — mysqldump + gzip 压缩 + 本地保留 + TOS 上传

用法:
    python -m db.backup          # 手动执行一次备份
    python -m db.backup --no-upload  # 仅本地备份不上传云端
"""
import os
import sys
import gzip
import shutil
import logging
import subprocess
import argparse
from datetime import datetime

logger = logging.getLogger(__name__)

ROOT = os.path.dirname(os.path.dirname(__file__))


def find_mysqldump() -> str:
    path = os.getenv("MYSQLDUMP_PATH", "")
    if path and os.path.isfile(path):
        return path
    # 搜索 PATH
    for d in os.environ.get("PATH", "").split(os.pathsep):
        exe = os.path.join(d, "mysqldump.exe" if sys.platform == "win32" else "mysqldump")
        if os.path.isfile(exe):
            return exe
    # 常见安装路径
    candidates = [
        r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
        r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe",
    ] if sys.platform == "win32" else [
        "/usr/bin/mysqldump",
        "/usr/local/mysql/bin/mysqldump",
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    raise FileNotFoundError("找不到 mysqldump，请设置 MYSQLDUMP_PATH 环境变量")


def run_backup(config: dict, backup_dir: str, retention: int, upload: bool = True):
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ai_agent_backup_{timestamp}.sql"
    filepath = os.path.join(backup_dir, filename)

    mysqldump = find_mysqldump()
    cmd = [
        mysqldump,
        f"--host={config['host']}",
        f"--port={config['port']}",
        f"--user={config['user']}",
        f"--password={config['password']}",
        "--single-transaction",
        "--routines",
        "--triggers",
        "--hex-blob",
        "--default-character-set=utf8mb4",
        config["database"],
    ]
    logger.info("备份: %s → %s", config["host"], filepath)

    with open(filepath, "w", encoding="utf-8") as f:
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"mysqldump 失败: {proc.stderr}")

    # 压缩
    gz_path = filepath + ".gz"
    with open(filepath, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out)
    os.remove(filepath)

    size_kb = round(os.path.getsize(gz_path) / 1024, 1)
    print(f"✓ 备份完成: {os.path.basename(gz_path)} ({size_kb} KB)")

    # 上传到云存储
    if upload:
        from db.cloud_storage import get_cloud_storage
        storage = get_cloud_storage()
        if storage:
            remote_key = f"db_backups/{os.path.basename(gz_path)}"
            if storage.upload(gz_path, remote_key):
                print(f"✓ 已上传到 TOS: {remote_key}")
            else:
                print("⚠ TOS 上传失败，仅保留本地备份")
        else:
            print("⚠ 云存储未配置，跳过上传")

    # 清理旧备份
    cleanup(backup_dir, retention)


def cleanup(backup_dir: str, retention: int):
    prefix = "ai_agent_backup_"
    files = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith(prefix) and f.endswith(".sql.gz")],
        reverse=True,
    )
    for old in files[retention:]:
        path = os.path.join(backup_dir, old)
        os.remove(path)
        print(f"  已清理旧备份: {old}")


def main():
    parser = argparse.ArgumentParser(description="数据库备份")
    parser.add_argument("--no-upload", action="store_true", help="不上传到云存储")
    args = parser.parse_args()

    from utils.sensitive_data import get_mysql_config
    from config.settings import BACKUP_DIR, BACKUP_RETENTION_COUNT

    config = get_mysql_config()
    print(f"备份 {config['host']}:{config['port']}/{config['database']}")
    run_backup(config, BACKUP_DIR, BACKUP_RETENTION_COUNT, upload=not args.no_upload)


if __name__ == "__main__":
    main()
