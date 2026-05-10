import io
import asyncio
import base64
import logging
from PIL import Image
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from spiderlx.core.browser_manager import browser_manager
from api.v1.middleware import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/browser", tags=["browser"])

_SAFE_ERROR = "请求处理失败，请稍后重试"


@router.post("/start")
async def start_browser(request: Request):
    """启动浏览器"""
    require_admin(request)
    try:
        result = browser_manager.start()
        logger.info("浏览器启动: %s → %s", request.state.username, result)
        return {"status": "ok", "message": result}
    except Exception as e:
        logger.error("浏览器启动失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.post("/stop")
async def stop_browser(request: Request):
    """关闭浏览器"""
    require_admin(request)
    try:
        result = browser_manager.stop()
        logger.info("浏览器关闭: %s → %s", request.state.username, result)
        return {"status": "ok", "message": result}
    except Exception as e:
        logger.error("浏览器关闭失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.get("/status")
async def browser_status(request: Request):
    """获取浏览器状态（仅 admin）"""
    require_admin(request)
    s = {"running": browser_manager.running, "url": browser_manager.current_url, "title": browser_manager.current_title}
    return s


@router.get("/screenshot")
async def browser_screenshot(request: Request):
    """获取当前浏览器截图（Base64，仅 admin）"""
    require_admin(request)
    try:
        png = browser_manager.screenshot()
        return {"screenshot": base64.b64encode(png).decode()}
    except RuntimeError:
        raise HTTPException(status_code=400, detail="浏览器未启动")
    except Exception as e:
        logger.error("浏览器截图失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.get("/stream")
async def browser_stream(request: Request, interval: float = Query(0.1, ge=0.01, le=0.6, description="帧间隔(秒)")):
    """SSE 浏览器截图实时推流（仅 admin，CDP截图 + JPEG）"""
    require_admin(request)
    logger.info("浏览器截图流已连接, interval=%s", interval)
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
                    logger.error("浏览器流截图失败: %s", e)
                    yield f"data: ERROR:{_SAFE_ERROR}\n\n"

                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
