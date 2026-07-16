"""纯计算 — 零依赖。"""
from typing import List


def add(a: float, b: float) -> float:
    return a + b


def multiply(a: float, b: float) -> float:
    return a * b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("除数不能为0")
    return a / b


def average(numbers: List[float]) -> float:
    if not numbers:
        raise ValueError("列表不能为空")
    return sum(numbers) / len(numbers)


def percentage(value: float, total: float) -> float:
    if total == 0:
        raise ValueError("总数不能为0")
    return (value / total) * 100
