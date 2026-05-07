import csv

import openpyxl
import pymysql

from utils.data_path import file_save_path, save_path


class SavedData:
    """
    保存得到的数据
    """
    __slots__ = ('name', 'path')

    def __init__(self, name):
        self.name = name
        self.path = file_save_path()  # 全部爬虫数据保存的原始位置

    def save_data(self):
        pass

    def save_data_html(self, data):
        path = f'{self.path}\\{self.name}.html'
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data)

    def save_data_csv(self, data_list, *args):
        with open(f'{self.path}\\csv\\{self.name}.csv', 'w', encoding='utf-8', newline='') as f:
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
        wb.save(f'{self.path}\\excel\\{self.name}.xlsx')

    def save_data_mysql(self, data_list):
        # 建立连接
        db = pymysql.connect(
            user='root',
            password='06172014@Lion',
            host='localhost',
            port=3306,
            database='mydb1'
        )
        print('数据库连接成功~~~~~')

        # 获取游标
        cursor = db.cursor()

        # 建表
        create_table_sql = f"""
            create table if not exists {self.name}(
            code varchar(10),
            sname varchar(20)
            );
            """
        cursor.execute(create_table_sql)
        print('数据表建立成功~~')

        # 插入数据，但是注意：增删改要注意事务的提交
        for sublist in data_list:
            insert_sql = f'insert into {self.name}(code,sname) value("{sublist[0]}","{sublist[1]}")'
            cursor.execute(insert_sql)
            db.commit()  # 事务提交

        print('数据插入成功~~~~')

        # 关闭链接
        cursor.close()
        db.close()


if __name__ == '__main__':
    save_path('None', 'data', '小猿', 'img')

