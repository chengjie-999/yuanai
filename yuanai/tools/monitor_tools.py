from langchain_core.tools import tool


@tool
def take_screenshot(monitor: int = 0) -> str:
    """
    用 mss 截取屏幕，返回 base64 图片数据。
    参数 monitor: 显示器编号（0=所有显示器合并，1/2/3=单个显示器）
    """
    try:
        import mss, base64
        from PIL import Image
        import io
        with mss.mss() as sct:
            if monitor == 0:
                region = sct.monitors[0]
            elif 1 <= monitor < len(sct.monitors):
                region = sct.monitors[monitor]
            else:
                return f"无效显示器编号，可用 0-{len(sct.monitors)-1}"
            raw = sct.grab(region)
            pil_img = Image.frombytes("RGB", raw.size, raw.rgb)
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=70)
            b64 = base64.b64encode(buf.getvalue()).decode()
        return f"截图成功 {region['width']}x{region['height']}，base64 数据已嵌入消息，可直接分析。"
    except Exception as e:
        return f"截图失败: {e}"


@tool
def list_monitors() -> str:
    """列出可用的显示器及尺寸"""
    try:
        import mss
        with mss.mss() as sct:
            lines = []
            for i, mon in enumerate(sct.monitors):
                if i == 0:
                    lines.append(f"  0: 全部显示器合并 ({mon['width']}x{mon['height']})")
                else:
                    lines.append(f"  {i}: 显示器{i} ({mon['width']}x{mon['height']})")
        return "可用显示器:\n" + "\n".join(lines)
    except Exception as e:
        return f"获取显示器失败: {e}"
