import os
import sys


# 打包 exe 的数据根目录（安装包化：数据不再散落在 exe 所在目录/桌面）
FROZEN_DATA_DIR = "XiaoYuanAI"
FROZEN_BIN_DIR = os.path.join(FROZEN_DATA_DIR, "bin")


def frozen_data_root() -> str:
    """exe 模式的数据根：%LOCALAPPDATA%\XiaoYuanAI\（用户数据目录，固定不漂移）"""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    root = os.path.join(base, FROZEN_DATA_DIR)
    os.makedirs(root, exist_ok=True)
    return root


def is_frozen_in_install_dir() -> bool:
    """当前 exe 是否已在标准安装目录（bin 子目录内）"""
    if not getattr(sys, "frozen", False):
        return True
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    return os.path.basename(os.path.normpath(exe_dir)).casefold() == "bin"


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
    # Docker 容器中直接使用工作目录
    if os.getenv("APP_HOME"):
        return os.getenv("APP_HOME")
    # 打包 exe：数据根固定用户数据目录（安装包化 2026-10-16——
    # 桌面双击/快捷方式启动都不再把 data 散落到 exe 旁）
    if getattr(sys, "frozen", False):
        return frozen_data_root()
    script_path = os.getcwd()
    path_parts = script_path.split(os.sep)
    try:
        target_index = path_parts.index(project_name)
        project_path = os.sep.join(path_parts[:target_index + 1])
        return project_path
    except ValueError:
        return script_path


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
