from langchain_core.tools import tool


@tool
def fetch_url(url: str, retype: str = "text") -> str:
    """
    发送 HTTP GET 请求获取网页内容。
    参数 url: 目标 URL
    参数 retype: 返回类型（text=原始文本, json=解析JSON, content=二进制），默认 text
    返回响应内容（注意：返回结果可能包含cookie等敏感信息，请勿对外分享）。
    """
    try:
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        if retype == 'json':
            result = resp.text
        elif retype == 'content':
            import base64
            result = base64.b64encode(resp.content).decode()
        else:
            result = resp.text
        preview = result[:2000]
        code = resp.status_code
        return (
            f"✅ 获取成功 (HTTP {code}, {len(result)} 字符)\n"
            f"URL: {url}\n"
            f"--- 内容预览 ---\n{preview}" + ("\n...(截断)" if len(result) > 2000 else "")
        )
    except Exception as e:
        return f"❌ 请求失败: {e}"


@tool
def save_crawl_data(url: str, data: str, data_type: str = "text") -> str:
    """
    保存爬取的数据到本地文件和数据库。
    参数 url: 数据来源的 URL
    参数 data: 爬取到的原始数据内容
    参数 data_type: 数据类型（text/html/json），默认 text
    """
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
        return f"✅ 数据已保存 (id={r['id']}){' ⚠️ URL已存在，已更新' if r.get('duplicate') else ''}\n文件: {file_path}\n预览: {preview[:200]}..."
    except Exception as e:
        return f"❌ 保存失败: {e}"


@tool
def list_crawl_data(page: int = 1, limit: int = 10) -> str:
    """
    列出爬取历史记录。
    参数 page: 页码（从1开始）
    参数 limit: 每页条数
    """
    try:
        from db.session import get_db
        db = get_db()
        records, total = db.get_crawl_records(page=page, limit=limit)
        if not records:
            return "暂无爬取记录"
        lines = [f"📋 爬取记录（共 {total} 条，第 {page} 页）"]
        for r in records:
            lines.append(f"  [{r['id']}] {r['url']}")
            lines.append(f"      类型: {r['retype']} | 大小: {r['result_length']} 字符 | {r['create_time'][:16]}")
        return '\n'.join(lines)
    except Exception as e:
        return f"❌ 查询失败: {e}"


@tool
def get_crawl_detail(record_id: int) -> str:
    """
    查看单条爬取记录的完整内容。
    参数 record_id: 记录 ID
    """
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
        preview = content[:3000]
        return (
            f"📄 爬取记录 #{record_id}\n"
            f"URL: {record['url']}\n"
            f"类型: {record['retype']} | 大小: {record['result_length']} 字符\n"
            f"时间: {record['create_time']}\n"
            f"--- 内容预览 ---\n"
            f"{preview}" + ("\n...(内容过长，已截断)" if len(content) > 3000 else "")
        )
    except Exception as e:
        return f"❌ 读取失败: {e}"
