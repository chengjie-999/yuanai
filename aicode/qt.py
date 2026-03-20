import os
import PyQt6

# 获取 PyQt6 安装目录
pyqt6_dir = os.path.dirname(PyQt6.__file__)
print(f"PyQt6 安装目录：{pyqt6_dir}")

# 列出所有 QWebEngine 相关文件/文件夹
webengine_files = [f for f in os.listdir(pyqt6_dir) if "WebEngine" in f]
print("PyQt6 目录下的 WebEngine 相关内容：")
for f in webengine_files:
    print(f"- {f}")
    # 如果是文件夹，查看里面的文件
    if os.path.isdir(os.path.join(pyqt6_dir, f)):
        sub_files = os.listdir(os.path.join(pyqt6_dir, f))
        print(f"  子文件：{sub_files}")

# 正常结果应该包含：
# - QWebEngineWidgets（文件夹），且里面有 __init__.py、QWebEngineView.pyi 等
# 或 QWebEngineWidgets.pyd（Windows 编译文件）