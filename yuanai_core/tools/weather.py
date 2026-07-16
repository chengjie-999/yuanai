TOOL_CATEGORY = "general"

"""天气工具"""
from langchain_core.tools import tool


@tool
def get_today_temperature(city: str) -> str:
    """Get today's temperature. city: Chinese city name, e.g. 北京, 上海."""
    return f"当前{city}未接入天气 API"


@tool
def get_tomorrow_forecast(city: str) -> str:
    """Get tomorrow's weather forecast. city: Chinese city name."""
    return f"明日{city}未接入天气 API"
