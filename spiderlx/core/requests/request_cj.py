import os

from tqdm import tqdm  # 导入进度条库

# S1.5：下载类请求同样走 safe_fetch 收口（守卫 + 逐跳重校验 + 钉住 + 体积上限）
from spiderlx.core.requests.safe_fetch import safe_get

DOWNLOAD_MAX_BYTES = 512 * 1024 * 1024  # 下载类上限（仍封顶，防无限流）


def stream_download_with_tqdm(url, save_path, chunk_size=1024 * 1024):
    """
    优雅进度显示：带可视化进度条、下载速度、剩余时间
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36 "
    }

    # S1.5：save_path 固化（basename，防调用方传路径穿越）；目录不存在自动创建
    dir_name = os.path.dirname(os.path.abspath(save_path))
    os.makedirs(dir_name, exist_ok=True)
    safe_name = os.path.basename(save_path)
    if not safe_name or safe_name in (".", ".."):
        raise ValueError(f"非法保存路径: {save_path!r}")
    final_path = os.path.join(dir_name, safe_name)

    try:
        with tqdm(
                total=0,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc=safe_name,  # 进度条前缀（显示文件名）
                ncols=100,  # 进度条宽度
                colour="green"  # 进度条颜色
        ) as pbar:
            downloaded = [0]  # 闭包计数（tqdm 自动算 total）
            with open(final_path, "wb") as f:
                def _cb(chunk: bytes):
                    f.write(chunk)
                    f.flush()
                    downloaded[0] += len(chunk)
                    pbar.total = downloaded[0] + 1  # 未知总量：随进度增长
                    pbar.update(len(chunk))

                result = safe_get(url, headers=headers, timeout=30,
                                  max_bytes=DOWNLOAD_MAX_BYTES, stream_cb=_cb)
            result.raise_for_status()
            if result.truncated:
                raise ValueError(f"文件超过下载上限（{DOWNLOAD_MAX_BYTES} 字节），已中止")

        print(f"\n✅ 下载完成！文件保存至：{final_path}")

    except Exception as e:
        print(f"\n❌ 下载失败：{e}")
        # 清理不完整文件
        if os.path.exists(final_path):
            try:
                os.remove(final_path)
            except OSError:
                pass


if __name__ == '__main__':
    video_url = 'https://bj.bcebos.com/qfcd/doc/2024-06-19/%E6%A6%82%E7%8E%87%E8%AE%BA%E4%B8%8E%E6%95%B0%E7%90%86%E7%BB%9F%E8%AE%A1.pdf'

    stream_download_with_tqdm(video_url, "large_video.pdf")
