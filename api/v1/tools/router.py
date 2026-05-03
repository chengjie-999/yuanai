import json
from fastapi import APIRouter, HTTPException

from api.v1.models import ToolRequest, ToolResponse, ToolInfo
from yuanai.tools import all_tools

router = APIRouter(prefix="/tools", tags=["tools"])


def _find_tool(name: str):
    for t in all_tools:
        if t.name == name:
            return t
    return None


@router.get("/", response_model=list[ToolInfo])
async def list_tools():
    """列出所有可用工具"""
    result = []
    for t in all_tools:
        try:
            args_schema = t.args  # 兼容不同版本
        except Exception:
            args_schema = {}
        result.append({
            "name": t.name,
            "description": t.description or "",
            "args": args_schema,
        })
    return result


@router.post("/execute", response_model=ToolResponse)
async def execute_tool(req: ToolRequest):
    """执行指定工具"""
    tool = _find_tool(req.name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具 '{req.name}' 不存在，可用工具: {[t.name for t in all_tools]}")

    try:
        result = tool.invoke(req.args)
        return {"name": req.name, "result": str(result) if result is not None else ""}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"工具 '{req.name}' 执行失败: {str(e)}")
