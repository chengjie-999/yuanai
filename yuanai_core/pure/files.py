"""文件浏览 — 只读。"""
import os
from typing import List, Dict, Optional


def list_files(subdir: str = "") -> List[Dict]:
    """列出 data/ 目录下的文件和目录。"""
    from utils.data_path import root_path
    base = os.path.join(root_path(), "data")
    target = os.path.join(base, subdir) if subdir else base
    if not os.path.exists(target):
        return []
    items = []
    for name in sorted(os.listdir(target)):
        full = os.path.join(target, name)
        is_dir = os.path.isdir(full)
        size = 0 if is_dir else os.path.getsize(full)
        items.append({"name": name, "is_dir": is_dir, "size_kb": round(size / 1024, 1)})
    return items


def read_file_content(path: str) -> Optional[str]:
    """读取 data/ 下的文本文件。"""
    from utils.data_path import root_path
    base = os.path.realpath(root_path() + "/data")
    target = os.path.realpath(os.path.join(base, path))
    if not target.startswith(base + os.sep) or not os.path.isfile(target):
        return None
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".txt", ".csv", ".json", ".py", ".tsx", ".ts", ".css",
                    ".html", ".md", ".log", ".yml", ".yaml"):
        return None
    with open(target, "r", encoding="utf-8") as f:
        return f.read()
