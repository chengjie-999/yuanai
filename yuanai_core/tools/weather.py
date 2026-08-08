TOOL_CATEGORY = "general"

"""天气工具 — 基于 wttr.in 免费 API"""
import urllib.request
import urllib.parse
import json
from langchain_core.tools import tool


def _fetch_weather(city: str, days: int = 1) -> dict | None:
    """调用 wttr.in 获取天气"""
    try:
        encoded = urllib.parse.quote(city)
        url = f"https://wttr.in/{encoded}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "yuanai"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


@tool
def get_today_weather(city: str) -> str:
    """获取指定城市今天天气。city: 中文城市名，如 北京、上海、杭州。"""
    data = _fetch_weather(city)
    if not data:
        return f"暂时无法获取 {city} 的天气信息，请稍后重试"

    try:
        cur = data["current_condition"][0]
        area = data["nearest_area"][0]
        city_name = area["areaName"][0]["value"]
        weather_desc = cur["weatherDesc"][0]["value"]
        temp_c = cur["temp_C"]
        feels_like = cur["FeelsLikeC"]
        humidity = cur["humidity"]
        wind = cur["winddir16Point"]
        wind_speed = cur["windspeedKmph"]
        uv = cur["uvIndex"]

        return (
            f"{city_name} 当前天气：{weather_desc}\n"
            f"温度：{temp_c}°C（体感 {feels_like}°C）\n"
            f"湿度：{humidity}%  |  风速：{wind} {wind_speed}km/h  |  紫外线：{uv}"
        )
    except Exception:
        return f"获取 {city} 天气数据异常，请稍后重试"


@tool
def get_tomorrow_forecast(city: str) -> str:
    """获取指定城市明天天气预报。city: 中文城市名。"""
    data = _fetch_weather(city, days=2)
    if not data:
        return f"暂时无法获取 {city} 的天气预报，请稍后重试"

    try:
        area = data["nearest_area"][0]
        city_name = area["areaName"][0]["value"]

        forecasts = data.get("weather", [])
        if len(forecasts) < 2:
            return f"{city_name} 暂无明日预报数据"

        tmr = forecasts[1]
        date = tmr["date"]
        high = tmr["maxtempC"]
        low = tmr["mintempC"]
        avg = tmr["avgtempC"]
        descs = [h["weatherDesc"][0]["value"] for h in tmr["hourly"] if h["weatherDesc"]]
        main_desc = max(set(descs), key=descs.count) if descs else "未知"
        sun_hour = tmr.get("sunHour", "N/A")

        return (
            f"{city_name} 明天（{date}）天气：{main_desc}\n"
            f"温度：{low}°C ~ {high}°C（平均 {avg}°C）\n"
            f"日照时长：{sun_hour} 小时"
        )
    except Exception:
        return f"解析 {city} 明日预报失败，请稍后重试"
