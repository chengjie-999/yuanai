from langchain_core.tools import tool


@tool
def get_today_temperature(city: str) -> str:
    """查询城市今日气温
    参数：
        city: 城市名称，如北京、上海、广州（中文全称）
    返回：
        包含气温和天气的字符串
    """
    print('get_today_temperature正在被调用')
    return f"{city} 今日气温 150°C，晴"


@tool  # 新增天气工具示例
def get_tomorrow_forecast(city: str) -> str:
    """查询城市明日天气预报
    参数：
        city: 城市名称（中文全称）
    返回：
        明日天气和气温字符串
    """
    print('get_tomorrow_forecast正在被调用')
    return f"{city} 明日气温 170°C，多云转小雨"
