from langchain_core.tools import tool
from yuanai.pure.crawl import fetch_url as _fetch, parse_html as _parse


@tool
def fetch_url(url: str, retype: str = "text") -> str:
    """发送 HTTP GET 请求获取网页内容。参数 url: 目标 URL，retype: text/json/content。"""
    try:
        return _fetch(url, retype)
    except Exception as e:
        return f"❌ 请求失败: {e}"


@tool
def parse_html(html: str) -> str:
    """解析 HTML 内容，提取标题、正文和链接。参数 html: 原始 HTML 字符串。"""
    try:
        result = _parse(html)
        return (
            f"\U0001f4c4 标题: {result['title']}\n\n"
            f"\U0001f4dd 正文:\n{result['text'][:3000]}\n\n"
            f"\U0001f517 链接 ({len(result['links'])} 个):\n" +
            "\n".join(f"  - {l['text']}: {l['url']}" for l in result['links'][:30])
        )
    except Exception as e:
        return f"❌ 解析失败: {e}"


# ---- 以下工具依赖数据库/文件系统，保留在原处 ----

@tool
def save_crawl_data(url: str, data: str, data_type: str = "text") -> str:
    """保存爬取数据到本地文件和数据库。url: 来源 URL，data: 原始数据，data_type: text/html/json。"""
    try:
        import os, uuid
        from utils.data_path import root_path
        from db.session import get_db

        ext = '.html' if data_type in ('html', 'text') else '.json'
        raw = data.encode('utf-8')
        crawl_dir = os.path.join(root_path(), 'data', 'crawl')
        os.makedirs(crawl_dir, exist_ok=True)
        file_id = str(uuid.uuid4())[:8]
        file_path = os.path.join(crawl_dir, f"{file_id}{ext}")
        with open(file_path, 'wb') as f:
            f.write(raw)
        preview = raw.decode('utf-8', errors='replace')[:2000]
        db = get_db()
        r = db.save_crawl_record(url, data_type, file_path, preview, len(raw))
        return f"✅ 数据已保存 (id={r['id']}) 文件: {file_path}"
    except Exception as e:
        return f"❌ 保存失败: {e}"


@tool
def list_crawl_data(page: int = 1, limit: int = 10) -> str:
    """列出爬取历史记录。page: 页码，limit: 每页条数。"""
    try:
        from db.session import get_db
        db = get_db()
        records, total = db.get_crawl_records(page=page, limit=limit)
        if not records:
            return "暂无爬取记录"
        lines = [f"\U0001f4cb 爬取记录（共 {total} 条，第 {page} 页）"]
        for r in records:
            lines.append(f"  [{r['id']}] {r['url']}")
        return '\n'.join(lines)
    except Exception as e:
        return f"❌ 查询失败: {e}"


@tool
def get_crawl_detail(record_id: int) -> str:
    """查看单条爬取记录的完整内容。record_id: 记录 ID。"""
    try:
        import os
        from db.session import get_db
        db = get_db()
        record = db.get_crawl_record(record_id)
        if not record:
            return "❌ 记录不存在"
        file_path = record.get("file_path", "")
        if not file_path or not os.path.isfile(file_path):
            return "⚠️ 原始文件已丢失"
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return f"\U0001f4c4 #{record_id}\nURL: {record['url']}\n---\n{content[:3000]}"
    except Exception as e:
        return f"❌ 读取失败: {e}"
