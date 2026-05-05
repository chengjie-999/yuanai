import io
import asyncio
import base64
import mss
from PIL import Image
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.get("/screenshot")
async def monitor_screenshot(monitor: int = Query(0, description="显示器编号，0=所有显示器合并，1/2/3=单个显示器")):
    """用 mss 截取屏幕，返回 Base64"""
    try:
        with mss.mss() as sct:
            if monitor == 0:
                region = sct.monitors[0]
            elif 1 <= monitor < len(sct.monitors):
                region = sct.monitors[monitor]
            else:
                return {"status": "error", "detail": f"无效显示器编号，可用范围: 0-{len(sct.monitors)-1}"}

            raw = sct.grab(region)
            pil_img = Image.frombytes("RGB", raw.size, raw.rgb)
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=75)
            b64 = base64.b64encode(buf.getvalue()).decode()
            return {
                "status": "ok",
                "screenshot": b64,
                "monitor": monitor,
                "width": region["width"],
                "height": region["height"],
            }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/monitors")
async def monitor_list():
    """获取显示器列表"""
    try:
        with mss.mss() as sct:
            monitors = []
            for i, mon in enumerate(sct.monitors):
                if i == 0:
                    monitors.append({"monitor": 0, "width": mon["width"], "height": mon["height"], "label": "所有显示器"})
                else:
                    monitors.append({
                        "monitor": i,
                        "width": mon["width"],
                        "height": mon["height"],
                        "left": mon["left"],
                        "top": mon["top"],
                        "label": f"显示器{i}",
                    })
            return {"status": "ok", "monitors": monitors}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/stream")
async def monitor_stream(
    monitor: int = Query(0, description="显示器编号，0=所有显示器合并"),
    interval: float = Query(0.1, ge=0.01, le=0.6, description="帧间隔(秒)"),
):
    """SSE 实时屏幕推流（JPEG + 可调帧率）"""
    async def generate():
        try:
            with mss.mss() as sct:
                while True:
                    try:
                        if monitor == 0:
                            region = sct.monitors[0]
                        elif 1 <= monitor < len(sct.monitors):
                            region = sct.monitors[monitor]
                        else:
                            region = sct.monitors[0]

                        raw = sct.grab(region)
                        pil_img = Image.frombytes("RGB", raw.size, raw.rgb)
                        buf = io.BytesIO()
                        pil_img.save(buf, format="JPEG", quality=70)
                        b64 = base64.b64encode(buf.getvalue()).decode()

                        yield f"data: {b64}\n\n"
                    except Exception as e:
                        yield f"data: ERROR:{str(e)}\n\n"

                    await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
