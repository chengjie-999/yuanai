import requests
from typing import Literal, Union
from requests.exceptions import RequestException, JSONDecodeError

# 定义严格的参数类型：只能是 'text'/'json'/'content' 三者之一
from spiderlx.anti.cookie.core import local_cookies, selenium_cookie_to_header, selenium_cookie_to_requests_param

ReturnType = Literal['text', 'json', 'content']


def get_response_data(
        url: str,
        retype: ReturnType = 'text',
        **kwargs
) -> Union[str, dict, list, bytes]:
    """
    发送GET请求并按指定类型返回响应数据

    Args:
        url: 请求的URL地址
        retype: 返回数据类型，可选值：'text'(文本)、'json'(JSON解析后的数据)、'content'(二进制字节流)

    Returns:
        对应类型的响应数据：
        - 'text' → 字符串
        - 'json' → 字典/列表
        - 'content' → 字节流(bytes)

    Raises:
        RequestException: 网络请求失败（如连接超时、404/500等）
        JSONDecodeError: 指定'json'但响应不是合法JSON格式
    """
    headers = {
        'User-Agent': 'Mozilla / 5.0(Windows NT 10.0;Win64;x64) AppleWebKit /'
                      ' 537.36(KHTML, likeGecko) Chrome / 124.0.0.0Safari / 537.36'
    }
    # 1. 发送请求，添加超时控制（避免无限等待）
    try:
        resp = requests.get(url, headers=headers, timeout=10, **kwargs)
        # 2. 主动触发HTTP错误（如404/500会抛出异常，便于上层捕获）
        resp.raise_for_status()
    except RequestException as e:
        raise RequestException(f"请求URL失败：{url}，错误信息：{str(e)}") from e

    # 3. 按类型返回数据，逻辑清晰且容错
    if retype == 'text':
        return resp.text
    elif retype == 'json':
        try:
            return resp.json()
        except JSONDecodeError as e:
            raise JSONDecodeError(f"响应内容无法解析为JSON，URL：{url}", doc=resp.text, pos=0) from e
    elif retype == 'content':
        return resp.content
    # 4. 理论上不会走到这里（因Literal类型限制），做兜底防御
    else:
        raise ValueError(f"无效的retype值：{retype}，仅支持 'text'/'json'/'content'")


if __name__ == '__main__':
    requests_cookies = selenium_cookie_to_requests_param(
        cookie_source=local_cookies('知乎'),
        filter_domain=".zhihu.com"  # 只保留知乎域名的Cookie
    )
    r = get_response_data('https://www.zhihu.com/', cookies=requests_cookies)
    print(r)
