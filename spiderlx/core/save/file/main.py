import os
import uuid
import hashlib
import requests
import psycopg2
from datetime import datetime
from pathlib import Path

# ====================== 【你只需要改这里】 ======================
PG_CONFIG = {
    "host": "localhost",
    "dbname": "spider_data",
    "user": "postgres",
    "password": "111111",
    "port": 5432
}

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# 文件分类
TYPE_MAP = {
    "video": [".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv"],
    "img": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
    "doc": [".pdf", ".zip", ".rar", ".7z", ".txt", ".md", ".docx", ".xlsx"],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


# ====================== PostgreSQL 工具函数 ======================
def get_conn():
    return psycopg2.connect(**PG_CONFIG)


# 初始化表
def init_pg_table():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS spider_downloads (
            id SERIAL PRIMARY KEY,
            url TEXT UNIQUE NOT NULL,
            file_type VARCHAR(20),
            filename TEXT,
            save_path TEXT,
            file_size BIGINT,
            md5 VARCHAR(32),
            create_time TIMESTAMP DEFAULT NOW()
        );
    ''')
    conn.commit()
    cur.close()
    conn.close()


# 判断 URL 是否已存在
def is_url_exists(url):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM spider_downloads WHERE url = %s", (url,))
    exists = cur.fetchone() is not None
    cur.close()
    conn.close()
    return exists


# 写入 PG
def save_to_pg(data):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO spider_downloads 
        (url, file_type, filename, save_path, file_size, md5)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (
        data["url"],
        data["file_type"],
        data["filename"],
        data["save_path"],
        data["size"],
        data["md5"]
    ))
    conn.commit()
    cur.close()
    conn.close()


# ====================== 文件工具函数 ======================
def init_dirs():
    for t in ["video", "img", "doc", "other"]:
        (DATA_DIR / t).mkdir(parents=True, exist_ok=True)


def get_file_type(ext):
    ext = ext.lower()
    for t, exts in TYPE_MAP.items():
        if ext in exts:
            return t
    return "other"


def get_md5(content):
    return hashlib.md5(content).hexdigest()


def get_unique_name(ext):
    ts = int(datetime.now().timestamp())
    return f"{ts}_{uuid.uuid4()}{ext}"


# ====================== 下载核心 ======================
def download_file(url):
    if is_url_exists(url):
        print(f"✅ 已存在: {url}")
        return

    try:
        print(f"⏬ 下载中: {url}")
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()

        ext = os.path.splitext(url)[1] or ".bin"
        file_type = get_file_type(ext)

        # 读取文件
        content = b""
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            content += chunk

        md5 = get_md5(content)
        size = len(content)
        filename = get_unique_name(ext)
        save_path = str(DATA_DIR / file_type / filename)

        # 保存到本地
        with open(save_path, "wb") as f:
            f.write(content)

        # 保存信息到 PostgreSQL
        data = {
            "url": url,
            "file_type": file_type,
            "filename": filename,
            "save_path": save_path,
            "size": size,
            "md5": md5
        }
        save_to_pg(data)
        print(f"✅ 已保存: {save_path}\n")

    except Exception as e:
        print(f"❌ 失败: {url} | {str(e)}\n")


def batch_download(url_list):
    for url in url_list:
        download_file(url)


# ====================== 运行 ======================
if __name__ == "__main__":
    init_pg_table()  # 初始化 PG 表
    init_dirs()  # 创建本地文件夹

    # 你要爬的文件链接
    test_urls = [
        "https://www.baidu.com/img/PCtm_d9c8750bed0b3c7d089fa7d5572076dee.gif",
        # "https://example.com/1.mp4",
        # "https://example.com/2.pdf"
    ]
    batch_download(test_urls)
