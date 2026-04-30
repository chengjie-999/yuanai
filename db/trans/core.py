import sqlite3
import pymysql

# 1. SQLite 连接
sqlite_conn = sqlite3.connect("你的文件.db")
sqlite_cursor = sqlite_conn.cursor()

# 2. MySQL 连接
mysql_conn = pymysql.connect(
    host="localhost",
    user="root",
    password="你的密码",
    database="目标库名",
    charset="utf8mb4"
)
mysql_cursor = mysql_conn.cursor()

# 3. 指定要迁移的表名
table_name = "目标表名"

# 读取SQLite表数据
sqlite_cursor.execute(f"SELECT * FROM {table_name}")
rows = sqlite_cursor.fetchall()

# 获取字段数量
col_count = len(sqlite_cursor.description)
placeholders = ", ".join(["%s"] * col_count)

# 插入MySQL
insert_sql = f"INSERT INTO {table_name} VALUES ({placeholders})"
mysql_cursor.executemany(insert_sql, rows)

# 提交&关闭
mysql_conn.commit()
sqlite_conn.close()
mysql_conn.close()

print("迁移完成")