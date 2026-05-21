from typing import Optional, List, Union, Any

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from yuanai_core.tools import all_tools as tools
from utils.sensitive_data import get_api_key
from config.settings import MODEL_NAMES

dsllm = [m for m in MODEL_NAMES if 'deepseek' in m]
seed = [m for m in MODEL_NAMES if 'doubao' in m]


class ChatDeepSeek(ChatOpenAI):
    """DeepSeek V4 适配器：消息序列化时保留 reasoning_content，确保工具调用多轮回传不丢失"""

    def _convert_message_to_dict(self, message: BaseMessage) -> dict:
        msg_dict = super()._convert_message_to_dict(message)
        if isinstance(message, AIMessage):
            reasoning = message.additional_kwargs.get("reasoning_content")
            if reasoning:
                msg_dict["reasoning_content"] = reasoning
        return msg_dict


# ===================== 核心：通用模型调用（兼容纯文本/多模态） =====================
def call_llm(
        messages: List[Union[SystemMessage, HumanMessage]],
        model_name: str = "deepseek-chat",
        temperature: float = 0.1
) -> Optional[str]:
    llm: BaseLanguageModel = get_llm(
        model_name,
        temperature=temperature,
        verbose=False
    )
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
        return ChatDeepSeek(
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
