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
    files = _list(subdir)
    return '\n'.join(files) if files else "目录为空"


@tool
def read_data_file(path: str) -> str:
    """Read a file's content. path: relative or absolute file path."""
    content = _read(path)
    return content[:5000] if len(content) > 5000 else content
