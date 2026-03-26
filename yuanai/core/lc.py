from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from yuanai.tools import all_tools as tools
from utils.sensitive_data import get_api_key
import sys

def get_llm(model='deepseek-chat', **kwargs):
    dsllm = ['deepseek-chat', 'deepseek-coder', 'deepseek-reasoner']
    dsmm = ['deepseek-vl2']
    if model in dsllm:
        model_type = 'dsllm'
        ds_api_key = get_api_key(model_type)
        return ChatOpenAI(
            api_key=ds_api_key,
            base_url="https://api.deepseek.com/v1",
            model=model,
            **kwargs,
        )
    elif model in dsmm:
        model_type = 'dsmm'
        ds_api_key = get_api_key(model_type)
        return ChatOpenAI(
            api_key=ds_api_key,
            base_url="https://api.deepseek.com/v1",
            model=model,
            **kwargs,
        )
    else:
        raise ValueError(f"无效的model值：{model}")

def get_langgraph_agent(llm, tools):
    # 不添加任何额外参数，系统提示在调用时通过消息列表传入
    return create_react_agent(llm, tools)

# 可选测试函数（保持原样）
def ai_with_tools(question: str):
    llm = get_llm('deepseek-chat', temperature=1, verbose=False)
    agent = get_langgraph_agent(llm, tools)
    try:
        # 调用时传入包含系统提示的消息
        result = agent.invoke({
            "messages": [
                ("system", "你是一个能调用工具的助手"),
                ("user", question)
            ]
        })
        return result["messages"][-1].content
    except Exception as e:
        return f"抱歉，处理你的问题时出错了：{str(e)}"

if __name__ == "__main__":
    print(ai_with_tools("北京今天多少度？再算 100+200"))