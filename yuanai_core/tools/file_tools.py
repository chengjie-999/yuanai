TOOL_CATEGORY = "file"

from typing import Optional

from langchain_core.tools import tool
from yuanai_core.pure.files import list_files as _list, read_file_content as _read


@tool
def save_data_csv(name: str, data: str, headers: str = "") -> str:
    """Save data as CSV file. name: filename (may include data/file/csv/ prefix; files are always saved under data/file/csv/), data: CSV content, headers: optional comma-separated."""
    import os
    from utils.data_path import root_path
    from utils.safe import ensure_within, normalize_save_filename, verified_write
    base = os.path.realpath(os.path.join(root_path(), 'data', 'file', 'csv'))
    os.makedirs(base, exist_ok=True)
    try:
        fname = normalize_save_filename(name, base)
        path = ensure_within(base, os.path.join(base, fname))
    except ValueError as e:
        return f"文件名非法: {e}"
    content = (headers + '\n' + data) if headers else data
    # 写后回读校验：不一致抛 IOError（上游工具调用收到异常，而非静默丢数据）
    verified_write(path, content)
    size = os.path.getsize(path)
    return f"CSV 已保存: data/file/csv/{fname} ({size} bytes)"


@tool
def list_data_files(subdir: str = "") -> str:
    """List files in data directory. subdir: optional subdirectory relative to data/ (e.g. file/csv)."""
    try:
        files = _list(subdir)
        if not files:
            return "目录为空"
        lines = []
        for f in files:
            name = f.get("name", str(f)) if isinstance(f, dict) else str(f)
            if isinstance(f, dict) and f.get("is_dir"):
                name += "/"
            size = f" ({f.get('size_kb', 0):.1f}KB)" if isinstance(f, dict) and f.get("size_kb") else ""
            lines.append(name + size)
        return '\n'.join(lines)
    except Exception as e:
        return f"列出文件失败: {e}"


@tool
def read_data_file(path: Optional[str] = "") -> str:
    """Read a file's content. path: relative path under data/ (e.g. file/csv/x.csv, or the path returned by save_data_csv), or an absolute path inside data/."""
    if not path:
        return "请提供文件路径（data/ 目录下的相对路径，或保存消息里返回的路径）"
    content = _read(path)
    if content is None:
        return "文件不存在或不可读（仅可读 data/ 目录下的文本文件；.yuan 记忆请用 get_user_memory 工具）"
    return content[:5000] if len(content) > 5000 else content
