from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from spiderlx.core.requests.core import get_response_data

router = APIRouter()


class RequestParams(BaseModel):
    url: str = Field(..., description="请求的URL地址")
    retype: Literal['text', 'json', 'content'] = Field(
        default='text',
        description="返回数据类型: text(文本), json(JSON解析), content(二进制)"
    )


@router.post("/request")
async def spider_request(params: RequestParams):
    """
    爬虫请求接口
    发送GET请求并按指定类型返回响应数据
    """
    if get_response_data is None:
        raise HTTPException(status_code=500, detail="爬虫核心模块未找到")
    
    try:
        result = get_response_data(params.url, params.retype)
        return {
            "status": "success",
            "data": result,
            "url": params.url,
            "retype": params.retype
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/request")
async def spider_request_get(
    url: str,
    retype: str = 'text'
):
    """
    GET 方式的爬虫请求接口
    """
    if get_response_data is None:
        raise HTTPException(status_code=500, detail="爬虫核心模块未找到")
    
    if retype not in ['text', 'json', 'content']:
        raise HTTPException(status_code=400, detail="无效的retype值")
    
    try:
        result = get_response_data(url, retype)
        return {
            "status": "success",
            "data": result,
            "url": url,
            "retype": retype
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
