"""天气工具 — 占位实现，待接入真实天气 API"""

from langchain_core.tools import tool


@tool
def get_today_temperature(city: str) -> str:
    """查询城市今日气温（占位：当前返回固定假数据）
    参数：
        city: 城市名称，如北京、上海、广州（中文全称）
    返回：
        包含气温和天气的字符串
    """
    return f"（天气数据暂不可用）{city} 今日气温数据暂未接入实时 API，请稍后再试"


@tool
def get_tomorrow_forecast(city: str) -> str:
    """查询城市明日天气预报（占位：当前返回固定假数据）
    参数：
        city: 城市名称（中文全称）
    返回：
        明日天气和气温字符串
    """
    return f"（天气数据暂不可用）{city} 明日天气预报暂未接入实时 API，请稍后再试"
