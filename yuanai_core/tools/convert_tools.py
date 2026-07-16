TOOL_CATEGORY = "general"

"""Unit conversion tools"""
from langchain_core.tools import tool


@tool
def convert_temperature(value: float, from_unit: str, to_unit: str) -> str:
    """Convert temperature units. value: number, from_unit/to_unit: C/F/K."""
    v, f, t = float(value), from_unit.upper(), to_unit.upper()
    if f == t: return f"{v}{f} = {v}{t}"
    celsius = v if f == "C" else ((v - 32) * 5/9 if f == "F" else (v - 273.15 if f == "K" else None))
    if celsius is None: return f"不支持的单位: {f}, 可选 C/F/K"
    result = celsius if t == "C" else (celsius * 9/5 + 32 if t == "F" else (celsius + 273.15 if t == "K" else None))
    if result is None: return f"不支持的单位: {t}, 可选 C/F/K"
    return f"{v}{f} = {result:.2f}{t}"


_LENGTH = {"mm":0.001, "cm":0.01, "m":1, "km":1000, "in":0.0254, "ft":0.3048, "yd":0.9144, "mi":1609.344, "寸":0.0333, "尺":0.333, "里":500}
_WEIGHT = {"mg":1e-6, "g":0.001, "kg":1, "t":1000, "oz":0.02835, "lb":0.4536, "两":0.05, "斤":0.5}
_AREA = {"sqm":1, "sqkm":1e6, "ha":10000, "mu":666.67, "sqft":0.0929, "acre":4046.86, "平方米":1, "平方公里":1e6, "公顷":10000, "亩":666.67}


@tool
def convert_length(value: float, from_unit: str, to_unit: str) -> str:
    """Convert length. value: number, from_unit/to_unit: mm/cm/m/km/in/ft/yd/mi/寸/尺/里."""
    try:
        v, fl, tl = float(value), from_unit.lower(), to_unit.lower()
        if fl not in _LENGTH or tl not in _LENGTH: return f"支持: {', '.join(_LENGTH)}"
        return f"{v}{from_unit} = {v*_LENGTH[fl]/_LENGTH[tl]:.4f}{to_unit}"
    except: return "参数错误"


@tool
def convert_weight(value: float, from_unit: str, to_unit: str) -> str:
    """Convert weight. value: number, from_unit/to_unit: mg/g/kg/t/oz/lb/两/斤."""
    try:
        v, fl, tl = float(value), from_unit.lower(), to_unit.lower()
        if fl not in _WEIGHT or tl not in _WEIGHT: return f"支持: {', '.join(_WEIGHT)}"
        return f"{v}{from_unit} = {v*_WEIGHT[fl]/_WEIGHT[tl]:.4f}{to_unit}"
    except: return "参数错误"


@tool
def convert_area(value: float, from_unit: str, to_unit: str) -> str:
    """Convert area. value: number, from_unit/to_unit: 平方米/亩/公顷/sqkm/sqft/acre."""
    try:
        v, fl, tl = float(value), from_unit.lower(), to_unit.lower()
        if fl not in _AREA or tl not in _AREA: return f"支持: {', '.join(_AREA)}"
        return f"{v}{from_unit} = {v*_AREA[fl]/_AREA[tl]:.4f}{to_unit}"
    except: return "参数错误"
