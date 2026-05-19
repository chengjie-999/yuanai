import json
import logging
import time
from fastapi import APIRouter, HTTPException, Request

from api.v1.models import ToolRequest, ToolResponse, ToolInfo
from api.v1.middleware import require_admin
from yuanai_core.tools import all_tools

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tools", tags=["tools"])

_SAFE_ERROR = "工具执行失败"

CATEGORIES = {
    "calculate_sum": "计算", "calculate_multiply": "计算",
    "get_today_temperature": "天气", "get_tomorrow_forecast": "天气",
    "get_system_stats": "系统",
    "save_data_csv": "文件", "list_data_files": "文件", "read_data_file": "文件",
    "save_crawl_data": "数据采集", "list_crawl_data": "数据采集", "get_crawl_detail": "数据采集",
    "fetch_url": "数据采集",
    "parse_html": "数据采集",
}

# 仅 admin 可用的工具
ADMIN_TOOLS = {
    "save_data_csv", "list_data_files", "read_data_file",
    "save_crawl_data", "list_crawl_data", "get_crawl_detail",
    "fetch_url",
    "parse_html",
}


def _find_tool(name: str):
    for t in all_tools:
        if t.name == name:
            return t
    return None


@router.get("/", response_model=list[ToolInfo])
async def list_tools(request: Request):
    """列出所有可用工具"""
    result = []
    for t in all_tools:
        try:
            args_schema = t.args
        except Exception:
            args_schema = {}
        result.append({
            "name": t.name,
            "description": t.description or "",
            "args": args_schema,
            "category": CATEGORIES.get(t.name, "其他"),
            "admin_only": t.name in ADMIN_TOOLS,
        })
    return result


@router.post("/execute", response_model=ToolResponse)
async def execute_tool(req: ToolRequest, request: Request):
    """执行指定工具"""
    tool = _find_tool(req.name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具 '{req.name}' 不存在")

    if req.name in ADMIN_TOOLS:
        require_admin(request)

    t0 = time.time()
    try:
        result = tool.invoke(req.args)
        elapsed = round(time.time() - t0, 3)
        logger.info("工具执行: %s args=%s → %.3fs", req.name, req.args, elapsed)
        return {"name": req.name, "result": str(result) if result is not None else ""}
    except Exception as e:
        elapsed = round(time.time() - t0, 3)
        logger.exception("工具失败: %s → %.3fs", req.name, elapsed)
        raise HTTPException(status_code=400, detail=_SAFE_ERROR)
