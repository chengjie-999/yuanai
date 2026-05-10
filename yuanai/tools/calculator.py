from langchain_core.tools import tool
from yuanai.pure.calculate import add, multiply  # noqa: F401 — 供外部 import


@tool
def calculate_sum(a: int, b: int) -> int:
    """计算两个整数的和。参数 a: 第一个整数，b: 第二个整数。返回求和结果。"""
    return add(a, b)


@tool
def calculate_multiply(a: int, b: int) -> int:
    """计算两个整数的乘积。参数 a: 第一个整数，b: 第二个整数。返回乘积结果。"""
    return multiply(a, b)
