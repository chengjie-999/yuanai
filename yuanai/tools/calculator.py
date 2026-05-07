from langchain_core.tools import tool


@tool
def calculate_sum(a: int, b: int) -> int:
    """计算两个整数的和
    参数：
        a: 第一个整数
        b: 第二个整数
    返回：
        两个数的求和结果
    """
    print('calculate_sum正在被调用')
    return a + b


@tool  # 新增计算工具示例
def calculate_multiply(a: int, b: int) -> int:
    """计算两个整数的乘积
    参数：
        a: 第一个整数
        b: 第二个整数
    返回：
        两个数的乘积结果
    """
    print('calculate_multiply正在被调用')
    return a * b
