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
    video_url = 'https://upos-sz-estgcos.bilivideo.com/upgcxcode/83/42/34159464283/34159464283-1-16.mp4?e' \
                '=ig8euxZM2rNcNbRVhwdVhwdlhWdVhwdVhoNvNC8BqJIzNbfq9rVEuxTEnE8L5F6VnEsSTx0vkX8fqJeYTj_lta53NCM=&trid' \
                '=2a2948e275104557b1981efc47cb641h&oi=0x240e087808fb1efc01475aa60e166fe2&nbs=1&platform=html5&gen' \
                '=playurlv3&og=cos&mid=0&deadline=1763906034&uipk=5&os=estgcos&upsig=d71949b6a51c1a6e0f7edd41a6ee3cce' \
                '&uparams=e,trid,oi,nbs,platform,gen,og,mid,deadline,uipk,' \
                'os&bvc=vod&nettype=0&bw=366258&dl=0&f=h_0_0&agrr=0&buvid=&build=0&orderid=0,1 '

    stream_download_with_tqdm(video_url, "large_video.mp4")
