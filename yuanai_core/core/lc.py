from typing import Optional, List, Union

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from utils.sensitive_data import get_api_key
from config.settings import MODEL_NAMES

dsllm = [m for m in MODEL_NAMES if 'deepseek' in m]
seed = [m for m in MODEL_NAMES if 'doubao' in m]


def call_llm(
        messages: List[Union[SystemMessage, HumanMessage]],
        model_name: str = "deepseek-chat",
        temperature: float = 0.1
) -> Optional[str]:
    llm = get_llm(model_name, temperature=temperature, verbose=False)
    try:
        response = llm.invoke(messages)
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        print(f"❌ 模型调用失败：{str(e)}")
        return None


def get_llm(model='deepseek-chat', **kwargs):
    if model in dsllm:
        ds_api_key = get_api_key('dsllm')
        extra_params = {}
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
        seed_api_key = get_api_key('seed')
        return ChatOpenAI(
            api_key=seed_api_key,
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            model=model,
            **kwargs,
        )
    else:
        raise ValueError(f"无效的model值：{model}")


def get_langgraph_agent(llm, tools):
    return create_react_agent(llm, tools)


def ai_with_tools(question: str):
    llm = get_llm('deepseek-chat', temperature=1, verbose=False)
    agent = get_langgraph_agent(llm, tools)
    try:
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
