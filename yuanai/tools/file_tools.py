from langchain_core.tools import tool


@tool
def save_data_csv(name: str, data: str, headers: str = "") -> str:
    """
    保存数据为 CSV 文件。
    参数 name: 文件名（不含后缀）
    参数 data: CSV 内容，每行用换行分隔，每列用逗号分隔
    参数 headers: CSV 表头（可选），每列用逗号分隔
    """
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
    """
    列出 data/ 目录下的文件和目录。
    参数 subdir: 子目录路径（如 'qimg'、'file/csv'），空字符串表示根目录
    """
    try:
        import os
        from utils.data_path import root_path
        base = os.path.join(root_path(), 'data')
        target = os.path.join(base, subdir) if subdir else base
        if not os.path.exists(target):
            return f"❌ 目录不存在: data/{subdir}"
        items = []
        for name in sorted(os.listdir(target)):
            full = os.path.join(target, name)
            if os.path.isdir(full):
                items.append(f"  📁 {name}/")
            else:
                size = os.path.getsize(full)
                kb = round(size / 1024, 1)
                items.append(f"  📄 {name} ({kb} KB)")
        title = f"data/{subdir or '.'}"
        return f"📂 {title}\n" + "\n".join(items) if items else f"📂 {title}\n  (空)"
    except Exception as e:
        return f"❌ 读取失败: {e}"


@tool
def read_data_file(path: str) -> str:
    """
    读取 data/ 下文本文件的内容。
    参数 path: 相对 data/ 的文件路径（如 'file/csv/test.csv'、'qimg/meta.json'）
    支持 txt/csv/json/py/tsx/css/html/md 等文本格式。
    """
    try:
        import os
        from utils.data_path import root_path
        base = os.path.join(root_path(), 'data')
        target = os.path.normpath(os.path.join(base, path))
        if not target.startswith(base):
            return "❌ 路径越权"
        if not os.path.isfile(target):
            return "❌ 文件不存在"
        ext = os.path.splitext(path)[1].lower()
        if ext in ('.txt', '.csv', '.json', '.py', '.tsx', '.ts', '.css', '.html', '.md', '.log', '.yml', '.yaml'):
            with open(target, 'r', encoding='utf-8') as f:
                content = f.read()
            return f"📄 {path}\n---\n{content[:3000]}" + ("\n...(截断)" if len(content) > 3000 else "")
        return f"❌ 暂不支持预览 {ext} 文件"
    except Exception as e:
        return f"❌ 读取失败: {e}"
