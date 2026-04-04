import mss
import mss.tools


def take_global_screenshot(save_path="screen.png"):
    """
    全局截全屏 → 给大模型看
    返回图片路径
    """
    with mss.mss() as sct:
        monitor = sct.monitors[0]  # 0 = 全屏
        img = sct.grab(monitor)
        mss.tools.to_png(img.rgb, img.size, output=save_path)

    return save_path


if __name__ == '__main__':
    p = take_global_screenshot()
    print(f"全局截图已保存到：{p}")
