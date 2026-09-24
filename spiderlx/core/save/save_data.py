"""爬虫数据保存（安全加固版）

- 文件名在构造期固化（safe_filename 白名单），保存路径 realpath 包含校验（防穿越）
- SQL 全部走 %s 占位符 + safe_ident 表名（防注入）
- 路径一律 os.path.join（原硬编码反斜杠在 Linux 容器会生成字面 `\data\file` 目录）
"""
import csv
import os

import openpyxl
import pymysql

from utils.data_path import file_save_path, save_path
from utils.safe import ensure_within, safe_filename, safe_ident


class SavedData:
    """
    保存得到的数据
    """
    __slots__ = ('name', 'path')

    def __init__(self, name):
        # 构造期固化安全名：白名单 + basename，杜绝路径穿越
        self.name = safe_filename(name)
        self.path = os.path.realpath(file_save_path())  # 全部爬虫数据保存的原始位置

    def _target(self, subdir: str, ext: str) -> str:
        """拼目标路径并做 realpath 包含校验；目录不存在自动创建"""
        base = os.path.join(self.path, subdir) if subdir else self.path
        target = os.path.realpath(os.path.join(base, f"{self.name}{ext}"))
        ensure_within(self.path, target)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        return target

    def save_data(self):
        pass

    def save_data_html(self, data):
        with open(self._target("", ".html"), 'w', encoding='utf-8') as f:
            f.write(data)

    def save_data_csv(self, data_list, *args):
        with open(self._target("csv", ".csv"), 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(args)
            writer.writerows(data_list)
            print('创建成功！')

    def save_data_excel(self, data_list):
        # 创建工作簿
        wb = openpyxl.Workbook()
        sheet = wb.active  # wb['Sheet']
        sheet.title = '新闻汇总'
        # 添加一条表头数据
        sheet.append(['新闻标题', '新闻类型', '新闻链接', '新闻发布时间'])
        for sublist in data_list:
            sheet.append(sublist)

        # 保存文件
        wb.save(self._target("excel", ".xlsx"))

    def save_data_mysql(self, data_list):
        # 建立连接（从统一配置获取）
        from utils.sensitive_data import get_mysql_config
        config = get_mysql_config()
        db = pymysql.connect(
            user=config["user"],
            password=config["password"],
            host=config["host"],
            port=config["port"],
            database=config["database"]
        )
        print('数据库连接成功~~~~~')

        try:
            # 获取游标
            cursor = db.cursor()

            # 表名白名单校验后进 SQL（防注入）
            table = safe_ident(self.name)

            # 建表
            create_table_sql = f"""
                create table if not exists `{table}`(
                code varchar(10),
                sname varchar(20)
                );
                """
            cursor.execute(create_table_sql)
            print('数据表建立成功~~')

            # 插入数据：%s 占位符 + 批量执行（防注入 + 原子性）
            rows = [(str(r[0]), str(r[1])) for r in data_list if len(r) >= 2]
            if rows:
                cursor.executemany(
                    f"INSERT INTO `{table}` (code, sname) VALUES (%s, %s)", rows)
            db.commit()  # 事务提交

            print('数据插入成功~~~~')
        finally:
            # 关闭链接
            cursor.close()
            db.close()


if __name__ == '__main__':
    save_path('None', 'data', '小猿', 'img')
