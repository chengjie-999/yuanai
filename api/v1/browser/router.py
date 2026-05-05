import io
import asyncio
import base64
from PIL import Image
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from spiderlx.core.browser_manager import browser_manager
from api.v1.middleware import require_admin

router = APIRouter(prefix="/browser", tags=["browser"])


@router.post("/start")
async def start_browser(request: Request):
    """启动浏览器"""
    require_admin(request)
    try:
        result = browser_manager.start()
        return {"status": "ok", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_browser(request: Request):
    """关闭浏览器"""
    require_admin(request)
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


@router.get("/stream")
async def browser_stream(interval: float = Query(0.1, ge=0.01, le=0.6, description="帧间隔(秒)")):
    """SSE 浏览器截图实时推流（CDP截图 + JPEG）"""
    async def generate():
        try:
            while True:
                try:
                    png = browser_manager.screenshot()
                    pil_img = Image.open(io.BytesIO(png))
                    buf = io.BytesIO()
                    pil_img.save(buf, format="JPEG", quality=70)
                    b64 = base64.b64encode(buf.getvalue()).decode()
                    yield f"data: {b64}\n\n"
                except RuntimeError:
                    yield "data: BROWSER_STOPPED\n\n"
                    break
                except Exception as e:
                    yield f"data: ERROR:{str(e)}\n\n"

                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
