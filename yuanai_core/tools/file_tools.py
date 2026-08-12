TOOL_CATEGORY = "file"

from langchain_core.tools import tool
from yuanai_core.pure.files import list_files as _list, read_file_content as _read


@tool
def save_data_csv(name: str, data: str, headers: str = "") -> str:
    """Save data as CSV file. name: filename, data: CSV content, headers: optional comma-separated."""
    import os
    from utils.data_path import root_path
    dir_path = os.path.join(root_path(), 'data', 'file', 'csv')
    os.makedirs(dir_path, exist_ok=True)
    path = os.path.join(dir_path, name)
    content = (headers + '\n' + data) if headers else data
    with open(path, 'w', encoding='utf-8-sig') as f:
        f.write(content)
    size = os.path.getsize(path)
    return f"CSV 已保存: {path} ({size} bytes)"


@tool
def list_data_files(subdir: str = "") -> str:
    """List files in data directory. subdir: optional subdirectory name."""
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
def read_data_file(path: str) -> str:
    """Read a file's content. path: relative or absolute file path."""
    content = _read(path)
    return content[:5000] if len(content) > 5000 else content
