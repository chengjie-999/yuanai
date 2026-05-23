import os

import requests

from spiderlx.anti.ip.core import CONFIG, get_random_proxy
from typing import Optional


def request_with_proxy() -> Optional[requests.Response]:
    """使用代理请求目标网址，包含重试机制"""
    if not CONFIG["TARGET_URL"]:
        print("错误：未配置目标请求网址")
        return None

    headers = {"User-Agent": CONFIG["USER_AGENT"]}
    retry_times = CONFIG["RETRY_TIMES"]

    for attempt in range(retry_times + 1):
        proxy = get_random_proxy()
        if proxy is None:
            print(f"第{attempt+1}次尝试：获取代理失败，跳过")
            continue

        proxies = {
            "http": proxy,
            "https": proxy
        }

        try:
            print(f"第{attempt+1}次尝试：使用代理请求目标网址")
            response = requests.get(
                CONFIG["TARGET_URL"],
                headers=headers,
                proxies=proxies,
                timeout=CONFIG["TIMEOUT"],
                verify=False
            )
            response.raise_for_status()
            print("目标网址请求成功")
            return response

        except requests.exceptions.RequestException as e:
            print(f"第{attempt+1}次尝试：请求失败：{str(e)}")
            if attempt == retry_times:
                return None
            # 重试前删除无效JSON文件
            if os.path.exists(CONFIG["IP_FILE_PATH"]):
                os.remove(CONFIG["IP_FILE_PATH"])


def main():
    """主函数：执行核心逻辑"""
    response = request_with_proxy()
    if response:
        print("响应内容：", response.content)
    else:
        print("所有请求尝试均失败")


if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    main()