import requests
from tqdm import tqdm  # 导入进度条库


def stream_download_with_tqdm(url, save_path, chunk_size=1024 * 1024):
    """
    优雅进度显示：带可视化进度条、下载速度、剩余时间
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36 "
    }

    try:
        response = requests.get(url, stream=True, headers=headers)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))  # 总大小（字节）

        # 初始化进度条：total=总大小，unit=字节，unit_scale=自动转换单位（KB/MB/GB）
        with tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc=save_path,  # 进度条前缀（显示文件名）
                ncols=100,  # 进度条宽度
                colour="green"  # 进度条颜色
        ) as pbar:
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        f.flush()
                        pbar.update(len(chunk))  # 关键：更新进度条（每次增加当前块的大小）

        print(f"\n✅ 下载完成！文件保存至：{save_path}")

    except requests.exceptions.RequestException as e:
        print(f"\n❌ 下载失败：{e}")


if __name__ == '__main__':
    video_url = 'https://bj.bcebos.com/qfcd/doc/2024-06-19/%E6%A6%82%E7%8E%87%E8%AE%BA%E4%B8%8E%E6%95%B0%E7%90%86%E7%BB%9F%E8%AE%A1.pdf'

    stream_download_with_tqdm(video_url, "large_video.mp4")
