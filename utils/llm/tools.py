from openai import OpenAI
import json

# 初始化客户端（替换为你的配置）
client = OpenAI(
    api_key="sk-d0b3bf178759483e8e40020f5d00ee02",
    base_url="https://api.deepseek.com"  # DeepSeek 地址，OpenAI 可省略
)


# ---------------------- 1. 你的工具函数 ----------------------
def get_today_temperature(city: str) -> str:
    """查询城市今日气温
    参数：city 城市名
    返回：气温字符串
    """
    print('get_today_temperature正在被调用')
    # 模拟天气接口（真实项目可替换为天气API）
    return f"{city} 今日气温 15°C，晴"


def calculate_sum(a: int, b: int) -> int:
    """计算两个数之和
    参数：a, b
    """
    print('calculate_sum正在被调用')
    return a + b


# ---------------------- 2. 定义 tools 参数（核心） ----------------------
# 把工具函数转换成 AI 能识别的 tools 格式
tools = [
    # 工具1：查气温
    {
        "type": "function",
        "function": {
            "name": "get_today_temperature",  # 必须和函数名完全一致
            "description": "查询指定城市的今日气温，返回包含气温和天气的字符串",  # 详细描述
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如北京、上海、广州（中文全称）"
                    }
                },
                "required": ["city"]  # 必填参数
            }
        }
    },
    # 工具2：计算求和
    {
        "type": "function",
        "function": {
            "name": "calculate_sum",  # 必须和函数名完全一致
            "description": "计算两个整数的和，返回求和结果",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {
                        "type": "integer",
                        "description": "第一个整数"
                    },
                    "b": {
                        "type": "integer",
                        "description": "第二个整数"
                    }
                },
                "required": ["a", "b"]  # 两个都是必填参数
            }
        }
    }
]


# ---------------------- 3. 核心函数：调用AI+执行工具 ----------------------
def ai_with_tools(question: str):
    # 第一步：调用AI，让模型判断是否需要调用工具
    response = client.chat.completions.create(
        model="deepseek-chat",  # DeepSeek 用这个，OpenAI 用 gpt-3.5-turbo
        messages=[{"role": "user", "content": question}],
        tools=tools,
        tool_choice="auto"  # 模型自动判断是否调用工具
    )

    # 提取AI的回复结果
    ai_message = response.choices[0].message
    print('【第一次回复】', ai_message)
    final_answer = ""

    # 第二步：判断AI是否要调用工具
    if hasattr(ai_message, "tool_calls") and ai_message.tool_calls:
        # 遍历所有工具调用指令（通常只有1个）
        for tool_call in ai_message.tool_calls:
            # 获取工具名称和参数
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            # 第三步：执行对应的工具函数
            if tool_name == "get_today_temperature":
                # 调用查气温函数
                result = get_today_temperature(**tool_args)
            elif tool_name == "calculate_sum":
                # 调用求和函数
                result = calculate_sum(**tool_args)
            else:
                result = f"未知工具：{tool_name}"

            # 第四步：把工具执行结果返回给AI，生成最终回复
            messages = [
                {"role": "user", "content": question},
                ai_message,  # AI的工具调用指令
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": str(result)  # 工具执行结果
                }
            ]

            # 再次调用AI，生成最终回复
            final_response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages
            )
            print('【第二次回复】')
            final_answer = final_response.choices[0].message.content
    else:
        # AI不需要调用工具，直接返回文本回复
        final_answer = ai_message.content

    return final_answer


# ---------------------- 4. 测试调用 ----------------------
if __name__ == "__main__":
    # 测试1：调用查气温工具
    print("测试1 - 查气温：")
    print(ai_with_tools("北京今天多少度？"))
    print("-" * 50)

    # 测试2：调用求和工具
    print("测试2 - 计算求和：")
    print(ai_with_tools("计算 100 + 200 等于多少？"))
    print("-" * 50)

    # 测试3：不需要调用工具（普通对话）
    print("测试3 - 普通对话：")
    print(ai_with_tools("你好！"))