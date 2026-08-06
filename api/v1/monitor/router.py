from fastapi import APIRouter, Request
from pydantic import BaseModel

from api.v1.middleware import require_admin
from api.v1.monitor.watcher import get_monitor

router = APIRouter(prefix="/monitor", tags=["monitor"])


class FileChangeReport(BaseModel):
    filepath: str
    status: str = "M"          # M=modified, A=added, D=deleted
    lines_added: int = 0
    lines_removed: int = 0


@router.get("/snapshot")
async def monitor_snapshot(request: Request, limit: int = 100):
    """单次获取全部监控数据（推荐）"""
    require_admin(request)
    return get_monitor().get_snapshot(min(limit, 200))


@router.post("/report")
async def monitor_report(request: Request, body: FileChangeReport):
    """Agent 上报文件变更"""
    require_admin(request)
    get_monitor().report_change(
        filepath=body.filepath,
        status=body.status,
        lines_added=body.lines_added,
        lines_removed=body.lines_removed,
    )
    return {"ok": True}


# ---- 以下端点保留兼容，推荐使用 /snapshot ----

@router.get("/status")
async def monitor_status(request: Request):
    require_admin(request)
    return get_monitor().get_status()


@router.get("/changes")
async def monitor_changes(request: Request, limit: int = 50):
    require_admin(request)
    monitor = get_monitor()
    return {"changes": monitor.get_changes(min(limit, 200)), "total": len(monitor.changes)}


@router.get("/timeline")
async def monitor_timeline(request: Request):
    require_admin(request)
    return {"timeline": get_monitor().get_timeline()}


@router.get("/file-types")
async def monitor_file_types(request: Request):
    require_admin(request)
    return {"distributions": get_monitor().get_file_type_distribution()}


@router.get("/top-files")
async def monitor_top_files(request: Request, top_n: int = 10):
    require_admin(request)
    return {"top_files": get_monitor().get_most_changed_files(min(top_n, 50))}


@router.post("/start")
async def monitor_start(request: Request):
    require_admin(request)
    monitor = get_monitor()
    if not monitor.is_running:
        monitor.start()
    return {"ok": True, "monitoring": monitor.is_running}


@router.post("/stop")
async def monitor_stop(request: Request):
    require_admin(request)
    monitor = get_monitor()
    monitor.stop()
    return {"ok": True, "monitoring": False}
