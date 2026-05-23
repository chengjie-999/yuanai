from typing import Optional, List, Union

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from utils.sensitive_data import get_api_key
from config.settings import MODEL_NAMES

dsllm = [m for m in MODEL_NAMES if 'deepseek' in m]
seed = [m for m in MODEL_NAMES if 'doubao' in m]

def _get_stored_key(provider: str) -> str | None:
    """从 data/models.json 读取存储的 API Key"""
    try:
        import json, os
        from utils.data_path import root_path
        path = os.path.join(root_path(), "data", "models.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("_apikeys", {}).get(provider)
    except Exception:
        pass
    return None


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


def get_llm(model='deepseek-chat', reasoning=True, **kwargs):
    if model in dsllm:
        ds_api_key = _get_stored_key("DeepSeek") or get_api_key('dsllm')
        extra_params = {}
        if reasoning and model in ['deepseek-v4-flash', 'deepseek-v4-pro']:
            extra_params["extra_body"] = {"reasoning_effort": "low"}
        elif reasoning and model == 'deepseek-reasoner':
            extra_params["extra_body"] = {"reasoning_effort": "high"}
        return ChatOpenAI(
            api_key=ds_api_key,
            base_url="https://api.deepseek.com/beta",
            model=model,
            **kwargs,
            **extra_params,
        )
    elif model in seed:
        seed_api_key = _get_stored_key("Doubao") or get_api_key('seed')
        return ChatOpenAI(
            api_key=seed_api_key,
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            model=model,
            **kwargs,
        )
    else:
        # 自定义模型：尝试从存储读取 Key，否则用模型 ID 推断
        provider = "Custom"
        from config.settings import MODELS
        if model in MODELS:
            provider = MODELS[model].get("provider", "Custom")
        custom_key = _get_stored_key(provider)
        if custom_key:
            # 默认用 OpenAI 兼容地址
            return ChatOpenAI(
                api_key=custom_key,
                base_url=kwargs.pop("base_url", "https://api.openai.com/v1"),
                model=model,
                **kwargs,
            )
        raise ValueError(f"未找到模型 {model} 的 API Key，请在 Agent 页面配置")


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
