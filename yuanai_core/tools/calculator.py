TOOL_CATEGORY = "general"

from langchain_core.tools import tool
from yuanai_core.pure.calculate import add, multiply, divide, average, percentage


@tool
def calculate_sum(a: float, b: float) -> float:
    """Sum two numbers. a, b: float."""
    return add(a, b)


@tool
def calculate_multiply(a: float, b: float) -> float:
    """Multiply two numbers. a, b: float."""
    return multiply(a, b)


@tool
def calculate_divide(a: float, b: float) -> float:
    """Divide a by b. a: dividend, b: divisor (non-zero)."""
    return divide(a, b)


@tool
def calculate_average(numbers: str) -> str:
    """Average of comma-separated numbers. numbers: e.g. '1,2,3,4,5'."""
    try:
        nums = [float(n.strip()) for n in numbers.split(",") if n.strip()]
        if not nums:
            return "请提供逗号分隔的数字"
        avg = average(nums)
        return f"平均值: {avg:.4f} | 总和: {sum(nums):.4f} | 个数: {len(nums)}"
    except ValueError as e:
        return f"计算失败: {e}"


@tool
def calculate_percentage(value: float, total: float) -> str:
    """Percentage = value/total * 100. value: part, total: whole."""
    try:
        pct = percentage(value, total)
        return f"{value}/{total} = {pct:.2f}%"
    except ValueError as e:
        return f"计算失败: {e}"
