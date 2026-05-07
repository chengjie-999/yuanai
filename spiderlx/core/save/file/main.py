import os
import hashlib
import requests
import pymysql
from urllib.parse import urlparse

# ==================== 配置区 ====================
from utils.data_path import root_path

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "你的MySQL密码",
    "database": "crawl",
    "charset": "utf8mb4"
}
BASE_SAVE_DIR = os.path.join(root_path(), "crawled_files")
CHUNK_SIZE = 1024 * 1024
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
}


# ================================================

def get_db_conn():
    """获取MySQL连接"""
    conn = pymysql.connect(**DB_CONFIG)
    return conn


def calc_md5(file_path):
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()


def get_safe_filename(url):
    """获取默认文件名"""
    return os.path.basename(urlparse(url).path) or "unknown_file"


def is_downloaded(url):
    """判断url是否已下载成功"""
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM crawled_files WHERE source_url=%s AND status='success'",
        (url,)
    )
    res = cur.fetchone()
    cur.close()
    conn.close()
    return res is not None


def insert_pending_task(url, file_name):
    """插入待下载记录"""
    conn = get_db_conn()
    cur = conn.cursor()
    sql = """
    INSERT INTO crawled_files 
    (source_url, file_name, file_type, save_path, status)
    VALUES (%s, %s, %s, %s, %s)
    """
    cur.execute(sql, (url, file_name, "unknown", "", "pending"))
    conn.commit()
    last_id = cur.lastrowid
    cur.close()
    conn.close()
    return last_id


def update_file_info(file_id, status, file_size, file_hash, save_path, file_type):
    """更新下载结果"""
    conn = get_db_conn()
    cur = conn.cursor()
    sql = """
    UPDATE crawled_files 
    SET status=%s, file_size=%s, file_hash=%s, save_path=%s, file_type=%s
    WHERE id=%s
    """
    cur.execute(sql, (status, file_size, file_hash, save_path, file_type, file_id))
    conn.commit()
    cur.close()
    conn.close()


def download_file(url):
    if is_downloaded(url):
        print(f"已跳过：{url}")
        return

    os.makedirs(BASE_SAVE_DIR, exist_ok=True)
    file_name = get_safe_filename(url)
    task_id = insert_pending_task(url, file_name)

    try:
        resp = requests.get(url, stream=True, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        file_type = resp.headers.get("Content-Type", "application/octet-stream")

        # 临时保存路径
        temp_path = os.path.join(BASE_SAVE_DIR, os.urandom(8).hex() + "_temp")
        with open(temp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)

        # 计算md5、大小
        file_size = os.path.getsize(temp_path)
        file_hash = calc_md5(temp_path)
        suffix = os.path.splitext(file_name)[-1]
        final_name = file_hash + suffix
        final_path = os.path.join(BASE_SAVE_DIR, final_name)
        os.rename(temp_path, final_path)

        # 更新mysql
        update_file_info(task_id, "success", file_size, file_hash, final_path, file_type)
        print(f"✅ 下载成功: {final_path}")

    except Exception as e:
        update_file_info(task_id, "failed", 0, "", "", "")
        print(f"❌ 下载失败 {url}：{str(e)}")


if __name__ == "__main__":
    test_list = [
        "https://www.python.org/static/img/python-logo.png",
        "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
    ]
    for item in test_list:
        download_file(item)
