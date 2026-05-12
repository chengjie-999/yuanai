import io
import asyncio
import base64
import hashlib
import logging
import os
from PIL import Image
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, FileResponse
from spiderlx.core.browser_manager import browser_manager
from api.v1.middleware import require_admin
from api.v1.auth.utils import create_sse_token
from utils.data_path import root_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/browser", tags=["browser"])

_SAFE_ERROR = "请求处理失败，请稍后重试"


@router.post("/sse-token")
async def get_sse_token(request: Request):
    """获取 SSE 连接用的短期令牌（5秒有效），避免 JWT 长期暴露在 URL 中"""
    require_admin(request)
    token = create_sse_token(request.state.user_id, request.state.role)
    return {"token": token}


@router.get("/qimg/{img_id}/{file_name}")
async def serve_qimg(img_id: str, file_name: str, request: Request):
    """提供题目截图（需要登录）"""
    # 路径安全检查
    if ".." in img_id or ".." in file_name or "/" in img_id or "\\" in img_id:
        raise HTTPException(status_code=400, detail="非法路径")
    file_path = os.path.join(root_path(), "data", "qimg", img_id, file_name)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path)


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
    """SSE 浏览器截图实时推流（仅 admin，CDP截图 + JPEG + 重复帧跳过）"""
    require_admin(request)
    logger.info("浏览器截图流已连接, interval=%s", interval)

    async def generate():
        last_hash = None
        idle_count = 0
        try:
            while True:
                if await request.is_disconnected():
                    logger.info("浏览器截图流客户端已断开")
                    break
                try:
                    png = browser_manager.screenshot()
                    raw_hash = hashlib.md5(png).digest()

                    # 重复帧跳过：画面未变化时降低推送频率（最多连续跳过 5 帧）
                    if raw_hash == last_hash and idle_count < 5:
                        idle_count += 1
                        await asyncio.sleep(interval)
                        continue
                    idle_count = 0
                    last_hash = raw_hash

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
