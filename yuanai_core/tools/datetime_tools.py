TOOL_CATEGORY = "general"

"""Date/time utilities"""
from datetime import datetime, timedelta
from langchain_core.tools import tool


@tool
def get_current_time(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Get current datetime. format: strftime pattern (default YYYY-MM-DD HH:MM:SS)."""
    return datetime.now().strftime(format)


@tool
def calculate_date_diff(date1: str, date2: str = "", unit: str = "days") -> str:
    """Days between two dates. date1/date2: YYYY-MM-DD (default date2=today), unit: days/months/years."""
    try:
        d1 = datetime.strptime(date1.strip(), "%Y-%m-%d")
        d2 = datetime.now() if not date2 else datetime.strptime(date2.strip(), "%Y-%m-%d")
        diff = abs((d2 - d1).days)
        if unit == "months":
            months = (d2.year - d1.year) * 12 + (d2.month - d1.month)
            return f"{abs(months)} 个月"
        elif unit == "years":
            return f"{diff / 365.25:.1f} 年"
        return f"{diff} 天"
    except ValueError:
        return "日期格式错误, 请用 YYYY-MM-DD"


@tool
def add_days(date: str, days: int) -> str:
    """Add/subtract days from a date. date: YYYY-MM-DD, days: int (negative=earlier)."""
    try:
        d = datetime.strptime(date.strip(), "%Y-%m-%d")
        return (d + timedelta(days=days)).strftime("%Y-%m-%d")
    except ValueError:
        return "日期格式错误, 请用 YYYY-MM-DD"


@tool
def get_weekday(date: str = "") -> str:
    """Get day of week. date: YYYY-MM-DD (default today)."""
    d = datetime.now() if not date else datetime.strptime(date.strip(), "%Y-%m-%d")
    wd = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return f"{d.strftime('%Y-%m-%d')} 是 {wd[d.weekday()]}"
