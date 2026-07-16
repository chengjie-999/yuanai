TOOL_CATEGORY = "crawl"

from langchain_core.tools import tool
from yuanai_core.pure.crawl import fetch_url as _fetch, parse_html as _parse


@tool
def fetch_url(url: str, retype: str = "text") -> str:
    """HTTP GET webpage content. url: target URL, retype: text/json/content."""
    try:
        return _fetch(url, retype)
    except Exception as e:
        return f"请求失败: {e}"


@tool
def parse_html(html: str) -> str:
    """Parse HTML, extract title/body/links. html: raw HTML string."""
    try:
        result = _parse(html)
        return (
            f"标题: {result['title']}\n\n"
            f"正文:\n{result['text'][:3000]}\n\n"
            f"链接 ({len(result['links'])} 个):\n" +
            "\n".join(f"  - {l['text']}: {l['url']}" for l in result['links'][:30])
        )
    except Exception as e:
        return f"解析失败: {e}"


@tool
def save_crawl_data(url: str, data: str, data_type: str = "text") -> str:
    """Save crawled data to file + DB. url: source URL, data: raw content, data_type: text/html/json."""
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
        return f"已保存 (id={r['id']}) 文件: {file_path}"
    except Exception as e:
        return f"保存失败: {e}"


@tool
def list_crawl_data(page: int = 1, limit: int = 10) -> str:
    """List crawl history. page: page number, limit: items per page."""
    try:
        from db.session import get_db
        db = get_db()
        records, total = db.get_crawl_records(page=page, limit=limit)
        if not records:
            return "暂无爬取记录"
        lines = [f"爬取记录 (共 {total} 条, 第 {page} 页)"]
        for r in records:
            lines.append(f"  [{r['id']}] {r['url']}")
        return '\n'.join(lines)
    except Exception as e:
        return f"查询失败: {e}"


@tool
def get_crawl_detail(record_id: int) -> str:
    """Get full content of a crawl record. record_id: record ID."""
    try:
        import os
        from db.session import get_db
        db = get_db()
        record = db.get_crawl_record(record_id)
        if not record:
            return "记录不存在"
        file_path = record.get("file_path", "")
        if not file_path or not os.path.isfile(file_path):
            return "原始文件已丢失"
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return f"#{record_id}\nURL: {record['url']}\n---\n{content[:3000]}"
    except Exception as e:
        return f"读取失败: {e}"


@tool
def check_url(url: str) -> str:
    """Check if URL is reachable. url: the URL to check."""
    import time
    try:
        import requests
        start = time.time()
        resp = requests.head(url, timeout=10, allow_redirects=True,
                            headers={"User-Agent": "Mozilla/5.0"})
        elapsed = (time.time() - start) * 1000
        return (
            f"可访问 (状态码: {resp.status_code})\n"
            f"响应: {elapsed:.0f}ms\n"
            f"最终URL: {resp.url}\n"
            f"Content-Type: {resp.headers.get('Content-Type', 'N/A')}"
        )
    except ImportError:
        import urllib.request
        try:
            start = time.time()
            req = urllib.request.Request(url, method='HEAD',
                                         headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=10)
            elapsed = (time.time() - start) * 1000
            return f"可访问 (状态码: {resp.getcode()})\n响应: {elapsed:.0f}ms"
        except Exception as e2:
            return f"不可访问: {e2}"
    except Exception as e:
        return f"不可访问: {e}"


@tool
def extract_html_table(html: str, table_index: int = 0) -> str:
    """Extract HTML table as CSV. html: HTML content, table_index: which table (0-based)."""
    try:
        import pandas as pd
        import io
        tables = pd.read_html(io.StringIO(html))
        if not tables:
            return "未找到 HTML 表格"
        if table_index >= len(tables):
            return f"只有 {len(tables)} 个表格, 序号 0-{len(tables)-1}"
        df = tables[table_index]
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        return f"表格 #{table_index+1}/{len(tables)}: {df.shape[0]}行x{df.shape[1]}列\n```csv\n{csv[:2000]}\n```"
    except ImportError:
        import re
        tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)
        if not tables or table_index >= len(tables):
            return "未找到 HTML 表格 (pip install pandas 以支持)"
        table_html = tables[table_index]
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.IGNORECASE)
        result = []
        for row in rows:
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL | re.IGNORECASE)
            cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            result.append(','.join(f'"{c}"' for c in cells))
        return f"表格 #{table_index+1}: {len(result)}行\n```csv\n" + '\n'.join(result[:20]) + "\n```"
