import csv
import os.path

import openpyxl
import pymysql


def make_dir(path):
    """
    初始化文件夹
    :param path: 项目根路径
    :return:
    """
    # 定义路径
    cookie_path = os.path.join(path, "web_cookie")
    os.makedirs(cookie_path, exist_ok=True)  # makedirs 也可创建多级目录，mkdir 只能创建单级

    data_path = os.path.join(path, "data")
    child_path = os.path.join(data_path, "file")
    file_types = ['csv', 'excel', 'img', 'media', 'txt']
    file_types = [os.path.join(child_path, file_type) for file_type in file_types]

    for path in file_types:
        os.makedirs(path, exist_ok=True)  # makedirs 也可创建多级目录，mkdir 只能创建单级


def root_path(project_name="my_spider"):
    script_path = os.getcwd()
    # print(script_path)
    # 按系统分隔符拆分路径
    path_parts = script_path.split(os.sep)
    # print(path_parts)

    # 找到"my_spider"的索引位置
    try:
        target_index = path_parts.index(project_name)
        # 截取到"spider_lx"的上一级目录
        project_path = os.sep.join(path_parts[:target_index + 1])
        # print("项目路径：", project_path)
        return project_path
    except ValueError:
        print(f"路径中未找到'{project_name}'目录")


def file_save_path(root=root_path()):
    path = root + r'\data\file'
    if not os.path.exists(path):
        make_dir(root)
    print("文件的保存位置：", path)
    return path


def img_save_path(name, root=root_path()):
    path = root + rf'\data\file\img\{name}'
    if not os.path.exists(path):
        make_dir(root)
    print("文件的保存位置：", path)
    return path


class SavedData:
    """
    保存得到的数据
    """
    __slots__ = ('name', 'path')

    def __init__(self, name):
        self.name = name
        self.path = file_save_path()  # 全部数据的保存位置

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
    sd = SavedData('666')
    sd.save_data_html('77777777777777')

