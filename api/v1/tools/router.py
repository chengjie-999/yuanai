import json
from fastapi import APIRouter, HTTPException, Request

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
    "get_system_stats": "系统",
    "take_screenshot": "监控", "list_monitors": "监控",
    "get_browser_status": "浏览器", "get_current_url": "浏览器", "take_browser_screenshot": "浏览器",
    "save_data_csv": "文件", "list_data_files": "文件", "read_data_file": "文件",
    "cookies_to_requests": "Cookie", "cookies_to_header": "Cookie",
    "save_crawl_data": "数据采集", "list_crawl_data": "数据采集", "get_crawl_detail": "数据采集",
    "fetch_url": "数据采集",
    "parse_html": "数据采集",
}

# 仅 admin 可用的工具
ADMIN_TOOLS = {
    "launch_new_browser", "close_browser", "open_website_by_code", "open_website_by_name",
    "open_custom_url", "refresh_page", "load_cookies", "save_cookies",
    "get_website_info",
    "get_task_cards", "start_task", "go_home", "save_page_html",
    "get_question_info", "submit_task", "zoom_question", "restore_question_view",
    "mark_question_correct", "confirm_rejection", "scroll_canvas", "click_canvas",
    "load_page_cookies", "save_page_cookies", "get_page_status",
    "save_data_csv", "list_data_files", "read_data_file",
    "cookies_to_requests", "cookies_to_header",
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
    from api.v1.middleware import require_admin
    tool = _find_tool(req.name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具 '{req.name}' 不存在")

    role = getattr(request.state, "role", "user")
    if role != "admin" and req.name not in ADMIN_TOOLS:
        raise HTTPException(status_code=403, detail="普通用户不能执行此工具")

    import time
    t0 = time.time()
    try:
        result = tool.invoke(req.args)
        elapsed = round(time.time() - t0, 3)
        print(f"🔧 工具执行: {req.name} args={req.args} → {elapsed}s")
        return {"name": req.name, "result": str(result) if result is not None else ""}
    except Exception as e:
        elapsed = round(time.time() - t0, 3)
        print(f"❌ 工具失败: {req.name} → {elapsed}s: {e}")
        raise HTTPException(status_code=400, detail=f"工具 '{req.name}' 执行失败: {str(e)}")
