import json
import os

import re
from typing import Dict, List, Union, Optional, Any

from utils.data_path import root_path


def local_cookies(name):
    # 构建Cookie文件完整路径
    cookie_file_path = os.path.join(root_path(), 'data', 'web_cookie', f'【{name}】cookies.json')

    # 如果Cookie文件不存在，先获取并保存
    if not os.path.exists(cookie_file_path):
        return None

    # 从JSON文件读取Cookie
    with open(cookie_file_path, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
        return cookies


def selenium_cookie_to_requests_param(
        cookie_source: Union[str, List[Dict[str, Any]]],
        ignore_keys: Optional[List[str]] = None,
        filter_domain: Optional[str] = None  # 新增：过滤指定域名的Cookie（适配Selenium多域名场景）
) -> Dict[str, str]:
    """
    以Selenium获取的Cookie为核心，转换为requests的cookies参数格式（键值对字典）
    兼容：Selenium的Cookie列表、浏览器请求头Cookie字符串、浏览器DevTools Cookie列表

    Args:
        cookie_source: Cookie来源（优先适配Selenium格式）：
            1. 列表：Selenium的driver.get_cookies()返回的Cookie列表（核心适配）
            2. 字符串：浏览器请求头复制的Cookie字符串
        ignore_keys: 可选，忽略的Cookie键（如统计类：["_ga", "_utm"]）
        filter_domain: 可选，只保留指定域名的Cookie（如".zhihu.com"，适配Selenium多域名Cookie）

    Returns:
        dict: 可直接传给requests.cookies参数的键值对字典

    Raises:
        TypeError: 传入的Cookie格式不支持
        ValueError: 无有效Cookie可解析
    """
    # 默认忽略的统计类Cookie
    ignore = ignore_keys or ["_ga", "_gat", "_utm", "UM_distinctid", "CNZZDATA", "Hm_lvt_"]
    cookie_dict = {}

    # 核心适配：处理Selenium返回的Cookie列表（包含domain/path/expiry等字段）
    if isinstance(cookie_source, list):
        for item in cookie_source:
            # 校验Selenium Cookie项的核心字段（必须有name/value）
            if not isinstance(item, dict) or "name" not in item or "value" not in item:
                continue

            # 提取核心字段并清洗
            key = str(item["name"]).strip()
            value = str(item["value"]).strip()

            # 过滤指定域名（适配Selenium多域名场景）
            if filter_domain and "domain" in item:
                cookie_domain = str(item["domain"]).strip()
                # 匹配规则：Cookie域名包含目标域名（如".zhihu.com"匹配"www.zhihu.com"）
                if filter_domain not in cookie_domain:
                    continue

            # 过滤空值、忽略指定键
            if key and value and key not in ignore:
                cookie_dict[key] = value

    # 兼容处理：浏览器请求头的Cookie字符串（兜底）
    elif isinstance(cookie_source, str):
        cookie_pairs = re.split(r';\s*', cookie_source.strip())
        for pair in cookie_pairs:
            if '=' not in pair:
                continue
            key, value = pair.split('=', 1)
            key = key.strip()
            value = value.strip()
            if key and value and key not in ignore:
                cookie_dict[key] = value

    # 不支持的格式
    else:
        raise TypeError(f"仅支持Selenium Cookie列表/浏览器Cookie字符串，当前传入：{type(cookie_source)}")

    # 校验解析结果
    if not cookie_dict:
        raise ValueError(
            "未解析到有效Cookie！请检查：\n"
            "1. Selenium Cookie是否包含name/value字段\n"
            "2. filter_domain是否匹配Cookie的domain\n"
            "3. ignore_keys是否过滤了所有Cookie"
        )

    return cookie_dict


def selenium_cookie_to_header(
        cookie_source: Union[str, List[Dict[str, Any]]],
        ignore_keys: Optional[List[str]] = None,
        filter_domain: Optional[str] = None
) -> Dict[str, str]:
    """
    以Selenium获取的Cookie为核心，转换为requests的headers格式（Cookie字符串）

    Args:
        同selenium_cookie_to_requests_param

    Returns:
        dict: 可直接传给requests.headers的{"Cookie": "xxx"}字典
        :param filter_domain:
        :param cookie_source:
        :param ignore_keys:
    """
    # 复用核心转换逻辑
    cookie_dict = selenium_cookie_to_requests_param(cookie_source, ignore_keys, filter_domain)
    # 拼接为标准Cookie请求头字符串
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
    return {"Cookie": cookie_str}


# ------------------- 完整使用示例（Selenium + requests） -------------------
if __name__ == "__main__":
    selenium_cookies = local_cookies('知乎')
    print("=== Selenium获取的原始Cookie ===")
    print(selenium_cookies[:2])  # 打印前2个Cookie示例

    # ========== 步骤2：转换为requests可用格式 ==========
    # 转换为requests.cookies参数（字典）
    requests_cookies = selenium_cookie_to_requests_param(
        cookie_source=selenium_cookies,
        filter_domain=".zhihu.com"  # 只保留知乎域名的Cookie
    )
    print("\n=== 转换为requests.cookies参数 ===")
    print(requests_cookies)

    # 转换为requests.headers参数（Cookie字符串）
    requests_header = selenium_cookie_to_header(
        cookie_source=selenium_cookies,
        filter_domain=".zhihu.com"
    )
    print("\n=== 转换为requests.headers参数 ===")
    print(requests_header)
