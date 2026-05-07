from fastapi import APIRouter, HTTPException
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
async def spider_request(params: RequestParams):
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
async def spider_batch(params: BatchRequestParams):
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
            preview = (str(data)[:500]) if data else ""
            results.append({"url": url, "status": "success", "preview": preview})
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
