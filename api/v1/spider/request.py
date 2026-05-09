from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Literal, Optional

from spiderlx.core.requests.core import get_response_data

router = APIRouter()


class RequestParams(BaseModel):
    url: str = Field(..., description="请求的URL地址")
    retype: Literal['text', 'json', 'content'] = Field('text', description="返回数据类型")
    method: Literal['GET', 'POST'] = Field('GET', description="请求方法")
    data: Optional[dict] = Field(None, description="POST 请求体（JSON）")
    cookie_site: str = Field('', description="Cookie 来源网站名")


@router.post("/request")
async def spider_request(params: RequestParams, request: Request):
    """发送HTTP请求并返回响应数据"""
    kwargs = {"method": params.method}
    if params.data:
        kwargs["json"] = params.data
    if params.cookie_site:
        from spiderlx.anti.cookie.core import local_cookies, selenium_cookie_to_requests_param
        cookies = local_cookies(params.cookie_site)
        if not cookies:
            return {"status": "error", "detail": f"未找到 [{params.cookie_site}] 的 Cookie"}
        kwargs["cookies"] = selenium_cookie_to_requests_param(cookies)
    try:
        result = get_response_data(params.url, params.retype, **kwargs)
        return {"status": "success", "data": result, "url": params.url, "retype": params.retype}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class BatchRequestParams(BaseModel):
    urls: list[str] = Field(..., description="URL 列表")
    retype: Literal['text', 'json', 'content'] = Field('text', description="返回数据类型")
    method: Literal['GET', 'POST'] = Field('GET', description="请求方法")
    data: Optional[dict] = Field(None, description="POST 请求体")
    cookie_site: str = Field('', description="Cookie 来源网站名")


@router.post("/batch")
async def spider_batch(params: BatchRequestParams, request: Request):
    """批量请求多个URL"""
    results = []
    for url in params.urls:
        kwargs = {"method": params.method}
        if params.data:
            kwargs["json"] = params.data
        if params.cookie_site:
            from spiderlx.anti.cookie.core import local_cookies, selenium_cookie_to_requests_param
            cookies = local_cookies(params.cookie_site)
            if cookies:
                kwargs["cookies"] = selenium_cookie_to_requests_param(cookies)
        try:
            data = get_response_data(url, params.retype, **kwargs)
            raw = str(data) if data else ""

            import os, uuid
            from utils.data_path import root_path
            from db.session import get_db
            crawl_dir = os.path.join(root_path(), 'data', 'crawl')
            os.makedirs(crawl_dir, exist_ok=True)
            ext = '.html' if params.retype == 'text' else '.json' if params.retype == 'json' else '.bin'
            file_id = str(uuid.uuid4())[:8]
            file_path = os.path.join(crawl_dir, f"{file_id}{ext}")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(raw)
            db = get_db()
            user_id = getattr(request.state, "user_id", None)
            r = db.save_crawl_record(url, params.retype, file_path, raw[:2000], len(raw), user_id)
            results.append({"url": url, "status": "success", "preview": raw[:500], "record_id": r["id"]})
        except Exception as e:
            results.append({"url": url, "status": "error", "detail": str(e)[:200]})
    return {"results": results}


@router.get("/request")
async def spider_request_get(url: str, retype: str = 'text'):
    """GET 方式的快速请求"""
    if retype not in ['text', 'json', 'content']:
        raise HTTPException(status_code=400, detail="无效的retype值")
    try:
        result = get_response_data(url, retype, method='GET')
        return {"status": "success", "data": result, "url": url, "retype": retype}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cookies")
async def list_cookies():
    """列出有 Cookie 文件的网站"""
    import os
    from utils.data_path import root_path
    cookie_dir = os.path.join(root_path(), 'data', 'web_cookie')
    if not os.path.exists(cookie_dir):
        return {"sites": []}
    sites = []
    for f in sorted(os.listdir(cookie_dir)):
        if f.endswith('.json'):
            name = f.replace('【', '').replace('】', '').replace('cookies.json', '').strip()
            sites.append(name)
    return {"sites": sites}


@router.get("/parse")
async def parse_html_content(url: str = "", html: str = "", record_id: int = 0):
    """解析 HTML 内容，提取标题、正文、链接。支持传 url（自动抓取）或直接传 html。"""
    try:
        from bs4 import BeautifulSoup
        from spiderlx.core.requests.core import get_response_data

        if not html and url:
            html = get_response_data(url, retype='text')
        soup = BeautifulSoup(html, 'html.parser')
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        text = soup.get_text(separator='\n', strip=True)[:5000]
        links = []
        for a in soup.find_all('a', href=True)[:50]:
            href = a['href']
            txt = a.get_text(strip=True)[:50]
            if href.startswith('http') or href.startswith('/'):
                links.append({"url": href, "text": txt or href[:30]})

        # 保存解析结果到数据库
        if record_id:
            try:
                from db.session import get_db
                db = get_db()
                db.save_parsed_data(record_id, title, text, links)
            except Exception:
                pass

        return {"title": title, "text": text[:5000], "links": links[:50]}
    except ImportError:
        return {"error": "需要安装 beautifulsoup4: pip install beautifulsoup4"}
    except Exception as e:
        return {"error": str(e)}
