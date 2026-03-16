from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.callbacks import BaseCallbackHandler
import sys

# 关键：从tools模块导入自动加载的所有工具，无需手动列工具
from tools import all_tools as tools


# 自定义回调处理器（保留之前的修复逻辑）
class CustomStdOutCallbackHandler(BaseCallbackHandler):
    def on_chain_start(self, serialized, inputs, **kwargs):
        inputs = inputs or {}
        print(f"\n=== 智能体开始执行 ===")
        print(f"用户输入：{inputs.get('input', '无')}")

    def on_tool_start(self, serialized, input_str, **kwargs):
        print(f"\n📌 开始调用工具：{serialized.get('name', '未知工具')}")
        print(f"工具参数：{input_str}")

    def on_tool_end(self, output, **kwargs):
        print(f"✅ 工具调用完成，结果：{output}")

    def on_chain_end(self, outputs, **kwargs):
        print(f"\n=== 智能体执行完成 ===")
        print(f"最终回答：{outputs.get('output', '无')}\n")


# 初始化LLM
llm = ChatOpenAI(
    api_key="sk-d0b3bf178759483e8e40020f5d00ee02",
    base_url="https://api.deepseek.com/v1",
    model="deepseek-chat",
    temperature=0,
    timeout=30,
    max_retries=2
)

# 配置提示词
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个能调用工具解决问题的助手，严格按照工具的参数要求调用工具，工具返回结果后要整理成自然语言回答用户。"),
    ("user", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# 创建智能体和执行器
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=False,
    callbacks=[CustomStdOutCallbackHandler()],
    handle_parsing_errors=True,
    max_iterations=5,
    return_intermediate_steps=False
)


# 封装调用函数
def ai_with_tools(question: str):
    try:
        result = agent_executor.invoke({"input": question, "agent_scratchpad": []})
        return result["output"]
    except Exception as e:
        print(f"❌ 调用出错：{str(e)}", file=sys.stderr)
        return f"抱歉，处理你的问题时出错了：{str(e)}"


# 测试调用
if __name__ == "__main__":
    print("===== 测试开始 =====")
    # 测试新增工具
    print("测试1 - 新增天气工具：")
    print(ai_with_tools("上海明天天气怎么样？"))
    print("|" * 100)

    print("测试2 - 新增计算工具：")
    print(ai_with_tools("计算 8 * 9 等于多少？"))
    print("|" * 100)

    # 原有测试
    print("测试3 - 原有工具：")
    print(ai_with_tools("北京今天多少度？再算 100+200"))
    print("===== 测试结束 =====")