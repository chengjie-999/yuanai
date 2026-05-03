import json
from fastapi import APIRouter, HTTPException

from api.v1.models import ToolRequest, ToolResponse, ToolInfo
from yuanai.tools import all_tools

router = APIRouter(prefix="/tools", tags=["tools"])

CATEGORIES = {
    "calculate_sum": "计算", "calculate_multiply": "计算",
    "get_today_temperature": "天气", "get_tomorrow_forecast": "天气",
    "retrieve_annotation_spec": "审核", "save_audit_feedback": "审核",
    "get_important_examples": "审核", "get_audit_feedback": "审核",
    "get_recent_feedbacks": "审核", "analyze_audit_errors": "审核",
    "launch_new_browser": "浏览器", "get_website_info": "浏览器",
    "open_website_by_code": "浏览器", "open_website_by_name": "浏览器",
    "open_custom_url": "浏览器", "refresh_page": "浏览器",
    "load_cookies": "浏览器", "save_cookies": "浏览器",
    "close_browser": "浏览器",
    "get_task_cards": "小猿任务", "start_task": "小猿任务",
    "go_home": "小猿任务", "save_page_html": "小猿任务",
    "get_question_info": "小猿任务", "submit_task": "小猿任务",
    "zoom_question": "小猿任务", "restore_question_view": "小猿任务",
    "mark_question_correct": "小猿任务", "confirm_rejection": "小猿任务",
    "scroll_canvas": "小猿任务", "click_canvas": "小猿任务",
    "load_page_cookies": "小猿任务", "save_page_cookies": "小猿任务",
    "get_page_status": "小猿任务",
}


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
            args_schema = t.args
        except Exception:
            args_schema = {}
        result.append({
            "name": t.name,
            "description": t.description or "",
            "args": args_schema,
            "category": CATEGORIES.get(t.name, "其他"),
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
