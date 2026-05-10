from langchain_core.tools import tool
from yuanai.pure.files import list_files as _list, read_file_content as _read


@tool
def save_data_csv(name: str, data: str, headers: str = "") -> str:
    """保存数据为 CSV 文件。name: 文件名，data: CSV 内容，headers: 可选表头。"""
    try:
        import os
        from utils.data_path import file_save_path
        save_dir = file_save_path()
        csv_dir = os.path.join(save_dir, 'csv')
        os.makedirs(csv_dir, exist_ok=True)
        path = os.path.join(csv_dir, f'{name}.csv')
        with open(path, 'w', encoding='utf-8', newline='') as f:
            if headers:
                f.write(headers + '\n')
            f.write(data)
        return f"✅ CSV 已保存: {path}"
    except Exception as e:
        return f"❌ 保存失败: {e}"


@tool
def list_data_files(subdir: str = "") -> str:
    """列出 data/ 目录下的文件和目录。subdir: 子目录路径（如 'qimg'、'file/csv'）。"""
    try:
        items = _list(subdir)
        if not items:
            return "（空）"
        lines = [f"\U0001f4c2 data/{subdir or '.'}"]
        for item in items:
            icon = "\U0001f4c1" if item["is_dir"] else "\U0001f4c4"
            lines.append(f"  {icon} {item['name']}{'/' if item['is_dir'] else ''} ({item['size_kb']} KB)")
        return '\n'.join(lines)
    except Exception as e:
        return f"❌ 读取失败: {e}"


@tool
def read_data_file(path: str) -> str:
    """读取 data/ 下文本文件的内容。path: 相对 data/ 的文件路径。"""
    try:
        content = _read(path)
        if content is None:
            return "❌ 文件不存在或格式不支持"
        return f"\U0001f4c4 {path}\n---\n{content[:3000]}"
    except Exception as e:
        return f"❌ 读取失败: {e}"
