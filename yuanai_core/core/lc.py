from typing import Optional, List, Union

from contextvars import ContextVar

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from utils.sensitive_data import get_api_key
from config.settings import MODEL_NAMES, REASONING_EFFORT

# 当前请求的推理强度（聊天框「快答/深思」开关；ws_client 按请求设置，
# 优先级：get_llm 显式参数 > 本 contextvar > settings.REASONING_EFFORT）
current_reasoning_effort: ContextVar[str] = ContextVar("lc_reasoning_effort", default="")

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


def get_llm(model='deepseek-chat', reasoning=True, reasoning_effort: Optional[str] = None, **kwargs):
    """LLM 工厂。reasoning_effort 优先级：显式参数 > 请求上下文（聊天框开关）> settings。"""
    if model in dsllm:
        ds_api_key = _get_stored_key("DeepSeek") or get_api_key('dsllm')
        extra_params = {}
        # 推理强度（模型升级弹性化）：按前缀匹配而非硬编码 id——
        # 新版本（deepseek-4.1 等）加入 models.json 后自动生效；
        # reasoner 系列恒 high（其专长）；其余 deepseek-* 用可配置强度
        if reasoning:
            effort = reasoning_effort or current_reasoning_effort.get() or REASONING_EFFORT
            if "reasoner" in model:
                extra_params["extra_body"] = {"reasoning_effort": "high"}
            elif model.startswith("deepseek-"):
                extra_params["extra_body"] = {"reasoning_effort": effort}
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
