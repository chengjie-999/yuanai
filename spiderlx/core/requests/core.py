import random
import time
import requests
from typing import Literal, Union
from requests.exceptions import RequestException, JSONDecodeError

from spiderlx.anti.ua import get_random_ua

ReturnType = Literal['text', 'json', 'content']


def get_response_data(
        url: str,
        retype: ReturnType = 'text',
        method: str = 'GET',
        max_retries: int = 2,
        **kwargs
) -> Union[str, dict, list, bytes]:
    """
    发送HTTP请求并按指定类型返回响应数据，内置反爬措施。
    Args:
        url: 请求的URL地址
        retype: 返回数据类型
        method: 请求方法（GET / POST）
        max_retries: 失败重试次数
    """
    delay = random.uniform(1.0, 3.0)
    time.sleep(delay)

    for attempt in range(max_retries + 1):
        try:
            headers = {
                'User-Agent': get_random_ua(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': 'https://www.google.com/',
            }
            if method == 'POST':
                resp = requests.post(url, headers=headers, timeout=15, **kwargs)
            else:
                resp = requests.get(url, headers=headers, timeout=15, **kwargs)
            resp.raise_for_status()
            break
        except RequestException as e:
            last_error = e
            if attempt < max_retries:
                wait = random.uniform(2.0, 5.0)
                time.sleep(wait)
            else:
                raise RequestException(f"请求URL失败（已重试{max_retries}次）：{url}，错误：{str(e)}") from e

    if retype == 'text':
        return resp.text
    elif retype == 'json':
        try:
            return resp.json()
        except JSONDecodeError as e:
            raise JSONDecodeError(f"响应内容无法解析为JSON，URL：{url}", doc=resp.text, pos=0) from e
    elif retype == 'content':
        return resp.content
    else:
        raise ValueError(f"无效的retype值：{retype}，仅支持 'text'/'json'/'content'")
