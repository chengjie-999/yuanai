from typing import Optional, List, Union

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from yuanai.tools import all_tools as tools
from utils.sensitive_data import get_api_key

dsllm = ['deepseek-chat', 'deepseek-coder', 'deepseek-reasoner', 'deepseek-v4-flash', 'deepseek-v4-pro']
seed = ['doubao-seed-2-0-pro-260215', 'doubao-seed-2-0-lite-260215']


# ===================== 核心：通用模型调用（兼容纯文本/多模态） =====================
def call_llm(
        messages: List[Union[SystemMessage, HumanMessage]],  # 核心修复：List替代list
        model_name: str = "deepseek-chat",  # 纯文本模型（无多模态API时用这个）
        temperature: float = 0.1
) -> Optional[str]:
    """
    调用LLM并返回结果（兼容纯文本/多模态模型）
    :param messages: 消息列表
    :param model_name: 模型名称（纯文本：deepseek-chat；多模态：deepseek-vl2）
    :param base_url: 模型接口地址
    :param temperature: 生成温度
    :return: 模型回答文本，失败返回None
    """
    # 1. 初始化模型
    llm: BaseLanguageModel = get_llm(
        model_name,
        temperature=temperature,
        verbose=False
    )

    # 2. 调用模型（增加异常捕获）
    try:
        response = llm.invoke(messages)
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        print(f"❌ 模型调用失败：{str(e)}")
        return None


def get_llm(model='deepseek-chat', **kwargs):
    if model in dsllm:
        model_type = 'dsllm'
        ds_api_key = get_api_key(model_type)
        
        extra_params = {}
        # 对于 deepseek-v4-flash 和 deepseek-v4-pro，使用低推理强度来减少 reasoning_content 生成
        if model in ['deepseek-v4-flash', 'deepseek-v4-pro']:
            extra_params["extra_body"] = {"reasoning_effort": "low"}
        elif model == 'deepseek-reasoner':
            extra_params["extra_body"] = {"reasoning_effort": "high"}
        
        return ChatOpenAI(
            api_key=ds_api_key,
            base_url="https://api.deepseek.com/beta",
            model=model,
            **kwargs,
            **extra_params,
        )
    elif model in seed:
        model_type = 'seed'
        return ChatOpenAI(
            api_key='39d1f61c-6a58-44e4-8d68-51bd4c31185d',
            base_url="https://ark.cn-beijing.volces.com/api/v3",
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
