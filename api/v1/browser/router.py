import base64
from fastapi import APIRouter, HTTPException
from spiderlx.core.browser_manager import browser_manager

router = APIRouter(prefix="/browser", tags=["browser"])


@router.post("/start")
async def start_browser():
    """启动浏览器"""
    try:
        result = browser_manager.start()
        return {"status": "ok", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_browser():
    """关闭浏览器"""
    try:
        result = browser_manager.stop()
        return {"status": "ok", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def browser_status():
    """获取浏览器状态"""
    return {
        "running": browser_manager.running,
        "url": browser_manager.current_url,
        "title": browser_manager.current_title,
    }


@router.get("/screenshot")
async def browser_screenshot():
    """获取当前浏览器截图（Base64）"""
    try:
        png = browser_manager.screenshot()
        return {"screenshot": base64.b64encode(png).decode()}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
