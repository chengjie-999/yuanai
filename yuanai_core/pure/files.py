"""文件浏览 — 只读。"""
import os
from typing import List, Dict, Optional


def _data_rel(path: str, base: str) -> Optional[str]:
    """外部路径 → data/ 下相对路径（与写工具共用 utils.safe.resolve_within 口径）。
    兼容模型带 'data/' 前缀（保存消息与工具文档写法不一致）；越界返回 None。"""
    from utils.safe import resolve_within
    try:
        rel = resolve_within(path, base)
    except ValueError:
        return None
    if rel == "data":
        return ""
    if rel.startswith("data/"):
        rel = rel[len("data/"):]
    return rel


def list_files(subdir: str = "") -> List[Dict]:
    """列出 data/ 目录下的文件和目录。"""
    from utils.data_path import root_path
    base = os.path.realpath(os.path.join(root_path(), "data"))
    rel = _data_rel(subdir or "", base)
    if rel is None:
        return []
    target = os.path.join(base, rel)
    if not os.path.isdir(target):
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
    rel = _data_rel(path, base)
    if rel is None:
        return None
    target = os.path.realpath(os.path.join(base, rel))
    if not target.startswith(base + os.sep) or not os.path.isfile(target):
        return None
    ext = os.path.splitext(rel)[1].lower()
    if ext not in (".txt", ".csv", ".json", ".py", ".tsx", ".ts", ".css",
                    ".html", ".md", ".log", ".yml", ".yaml"):
        return None
    with open(target, "r", encoding="utf-8") as f:
        return f.read()
