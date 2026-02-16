import os


def make_init_dir(path):
    """
    初始化系统文件夹
    :param path: 项目根路径
    :return:
    """
    # 1. cookie 文件夹
    cookie_path = os.path.join(path, "web_cookie")
    os.makedirs(cookie_path, exist_ok=True)  # makedirs 也可创建多级目录，mkdir 只能创建单级

    # 2. data 文件夹
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
        # 截取到"spiderlx"的上一级目录
        project_path = os.sep.join(path_parts[:target_index + 1])
        # print("项目路径：", project_path)
        return project_path
    except ValueError:
        print(f"路径中未找到'{project_name}'目录")


def save_path(file_name=None, *args):
    """
    文件的保存地址
    :param file_name:
    :param args: 项目文件下的目录
    :return:
    """
    root = root_path()
    save_dir = os.sep.join(args)
    # path = root + save_dir
    path = os.path.join(root, save_dir)
    if not os.path.exists(path):
        os.makedirs(path)
    path = os.path.join(path, file_name)
    print("文件的保存位置：", path)
    return path


def file_save_path(root=root_path(), *args):
    # 相对路径
    path = r'\data\file'
    path = os.path.join(root, path)
    if not os.path.exists(path):
        make_init_dir(root)
    print("文件的保存位置：", path)
    return path


def img_save_path(name, root=root_path()):
    path = root + rf'\data\file\img\{name}'
    if not os.path.exists(path):
        make_init_dir(root)
    print("文件的保存位置：", path)
    return path