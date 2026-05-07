import os
import random
import json
import requests
from typing import Dict, Optional

# 配置项：将文件后缀改为.json
from utils.data_path import root_path

r = os.path.join(root_path(), r"data\ip\ip_proxy.json")
CONFIG = {
    "API_URL": "",  # 第三方IP代理API地址
    "TARGET_URL": "www,baidu.com",  # 目标请求网址
    "IP_FILE_PATH": "ip_proxy.json",  # 改为JSON文件
    "USER_AGENT": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "TIMEOUT": 10,  # 请求超时时间（秒）
    "RETRY_TIMES": 2  # 请求失败重试次数
}


def get_ip_data() -> Optional[Dict]:
    """从第三方API获取IP代理数据，保存为JSON文件"""
    if not CONFIG["API_URL"]:
        print("错误：未配置第三方IP代理API地址")
        return None

    try:
        response = requests.get(
            CONFIG["API_URL"],
            timeout=CONFIG["TIMEOUT"],
            headers={"User-Agent": CONFIG["USER_AGENT"]}
        )
        response.raise_for_status()

        ip_data = response.json()
        # 校验数据格式
        if not isinstance(ip_data, dict) or "data" not in ip_data or "port" not in ip_data:
            print("错误：API返回数据格式不符合预期")
            return None

        # 直接写入JSON文件（无需转字符串）
        with open(CONFIG["IP_FILE_PATH"], "w", encoding="utf-8") as f:
            json.dump(ip_data, f, ensure_ascii=False, indent=2)  # indent美化格式，便于查看

        print("IP代理数据获取成功并保存为JSON文件")
        return ip_data

    except requests.exceptions.RequestException as e:
        print(f"请求第三方API失败：{str(e)}")
        return None
    except (IOError, OSError) as e:
        print(f"保存JSON文件失败：{str(e)}")
        return None


def get_random_proxy() -> Optional[str]:
    """从JSON文件读取IP代理数据，随机返回一个代理地址"""
    ip_data = None
    # 读取JSON文件（无需eval，直接解析）
    if os.path.exists(CONFIG["IP_FILE_PATH"]):
        try:
            with open(CONFIG["IP_FILE_PATH"], "r", encoding="utf-8") as f:
                ip_data = json.load(f)  # 直接加载JSON，安全且高效
        except json.JSONDecodeError as e:
            print(f"JSON文件解析失败（格式错误）：{str(e)}")
            os.remove(CONFIG["IP_FILE_PATH"])
        except (IOError, OSError) as e:
            print(f"读取JSON文件失败：{str(e)}")
            os.remove(CONFIG["IP_FILE_PATH"])

    # 本地无有效数据则重新获取
    if ip_data is None:
        ip_data = get_ip_data()
        if ip_data is None:
            return None

    # 校验数据并生成代理
    ip_list = ip_data.get("data", [])
    port = ip_data.get("port")
    if not ip_list or not port:
        print("错误：IP代理数据不完整")
        return None

    random_ip = random.choice(ip_list)
    proxy = f"https://{random_ip}:{port}"
    print(f"随机选中代理：{proxy}")
    return proxy


if __name__ == '__main__':
    proxy = get_random_proxy()
    print(proxy)
