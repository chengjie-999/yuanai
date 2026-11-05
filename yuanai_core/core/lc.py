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


def refresh_model_lists() -> None:
    """模型清单热更新（后台 add/delete/upgrade 模型后调用）：重算 dsllm/seed
    前缀通道，修「新加模型走不了 DeepSeek/豆包通道，重启才生效」的缺口"""
    global dsllm, seed
    from config.settings import MODEL_NAMES as _names
    dsllm = [m for m in _names if 'deepseek' in m]
    seed = [m for m in _names if 'doubao' in m]

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


def _agent_proxy_endpoint():
    """T5（2026-11-06）用户 Agent 云端代理：本机无 API key 时，LLM 走云端
    OpenAI 兼容代理（identity.server_url + agent_secret）。云端进程无 identity
    文件 → 返回 None 不受影响；有 key 的开发机不进入此分支（直连优先）。"""
    try:
        import json, os
        from utils.data_path import root_path
        path = os.path.join(root_path(), "data", "agent_identity.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            ident = json.load(f)
        server = str(ident.get("server_url") or "").strip()
        secret = str(ident.get("agent_secret") or "").strip()
        if not server or not secret:
            return None
        # identity 里可能是 ws:// 地址（ws_client 用），代理需 http(s)
        server = server.replace("ws://", "http://").replace("wss://", "https://")
        return (server.rstrip("/") + "/api/v1/agent/llm", secret)
    except Exception:
        return None


def call_llm(
        messages: List[Union[SystemMessage, HumanMessage]],
        model_name: str = "deepseek-flash",
        temperature: float = 0.1
) -> Optional[str]:
    llm = get_llm(model_name, temperature=temperature, verbose=False)
    try:
        response = llm.invoke(messages)
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        print(f"❌ 模型调用失败：{str(e)}")
        return None


def resolve_model_id(model: str) -> str:
    """模型 ID 归一化：退役 ID 路由 + 短名前缀匹配到注册表完整 ID。

    get_llm 调用它执行实际推理；自报注入（模型「如实回答自己是什么模型」）
    也必须用它——否则注入的字符串与实际调用的 ID 不一致（说一套跑一套）。
    """
    # 旧模型 ID 兼容（2026-10-16）：已退役 ID 自动路由到新 ID（升级知识表维护）——
    # 存量配置/历史数据里的旧 ID 不报错，静默走新模型
    from yuanai_core.pure.model_upgrades import MODEL_UPGRADES
    if model in MODEL_UPGRADES:
        model = MODEL_UPGRADES[model]["new"]
    # 短名解析（2026-10-14）：skills/*.yaml 用短名（doubao-seed-2-0-lite），
    # 注册表是完整 ID（doubao-seed-2-0-lite-260215）。前缀匹配替换——
    # 委派/@定向/计划执行器共用本工厂，此前短名落 custom 分支报「未找到 API Key」。
    if model not in dsllm and model not in seed:
        for m in seed + dsllm:
            if m.startswith(model) or model.startswith(m):
                model = m
                break
    return model


def get_llm(model='deepseek-flash', reasoning=True, reasoning_effort: Optional[str] = None,
            usage_purpose: str = "chat", **kwargs):
    """LLM 工厂。reasoning_effort 优先级：显式参数 > 请求上下文（聊天框开关）> settings。
    usage_purpose：用量记账用途（成本分析按用途拆分：chat/title_gen/memory_fold/
    planet_article/audit/embedding/mode_router 等；不传默认 chat）。"""
    model = resolve_model_id(model)
    # 流式调用自动开启 stream_usage：不开则响应无 usage，用量记账（token_usage 表）
    # 永远拿不到数据。DeepSeek/豆包 Ark 均已实测支持 stream_options.include_usage；
    # 调用方显式传 stream_usage 时以调用方为准。
    if kwargs.get("streaming") and "stream_usage" not in kwargs:
        kwargs["stream_usage"] = True
    if model in dsllm:
        ds_api_key = _get_stored_key("DeepSeek") or get_api_key('dsllm')
        ds_base_url = "https://api.deepseek.com/beta"
        # T5（2026-11-06）：本机无 key → 走云端代理（用户 Agent 默认链路）；
        # 代理模式下不挂本地记账回调——云端代理统一记账，防双计
        via_proxy = False
        if not ds_api_key:
            _proxy = _agent_proxy_endpoint()
            if _proxy:
                ds_base_url, ds_api_key = _proxy
                via_proxy = True
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
            base_url=ds_base_url,
            model=model,
            # B4 截断根因之一（2026-10-29）：未设 max_tokens 时网关默认 4096，
            # 长回答被 finish_reason=length 硬切；显式给足（deepseek 系上限 8K）
            max_tokens=kwargs.pop("max_tokens", 8192),
            callbacks=kwargs.pop("callbacks", None) or ([] if via_proxy else [_usage_cb(model, usage_purpose)]),
            **kwargs,
            **extra_params,
        )
    elif model in seed:
        seed_api_key = _get_stored_key("Doubao") or get_api_key('seed')
        seed_base_url = "https://ark.cn-beijing.volces.com/api/v3"
        via_proxy = False
        if not seed_api_key:
            _proxy = _agent_proxy_endpoint()
            if _proxy:
                seed_base_url, seed_api_key = _proxy
                via_proxy = True
        return ChatOpenAI(
            api_key=seed_api_key,
            base_url=seed_base_url,
            model=model,
            callbacks=kwargs.pop("callbacks", None) or ([] if via_proxy else [_usage_cb(model, usage_purpose)]),
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
            # C9（2026-10-29）出境开关：自定义模型 base_url 一律校验——
            # 默认白名单仅境内端点（DeepSeek/火山 Ark/本机联调），未知端点
            # fail-closed 拒绝路由（曾默认 api.openai.com/v1 直接出境）。
            from config.settings import LLM_BASE_URL_ALLOWLIST, OVERSEAS_BASE_URL_ALLOWED
            base_url = kwargs.pop("base_url", "https://api.deepseek.com/v1")
            if not OVERSEAS_BASE_URL_ALLOWED:
                host = ""
                try:
                    from urllib.parse import urlparse
                    host = (urlparse(base_url).hostname or "").lower()
                except Exception:
                    host = ""
                allowed = any(
                    host == p or host.endswith("." + p)
                    for p in LLM_BASE_URL_ALLOWLIST
                )
                if not allowed:
                    raise ValueError(
                        f"模型 {model} 的 base_url（{base_url}）不在境内端点白名单内，"
                        f"已拒绝路由（数据出境开关）。如该端点为合规境内网关，"
                        f"请将域名加入 LLM_BASE_URL_ALLOWLIST 环境变量。")
            return ChatOpenAI(
                api_key=custom_key,
                base_url=base_url,
                model=model,
                callbacks=kwargs.pop("callbacks", None) or [_usage_cb(model, usage_purpose)],
                **kwargs,
            )
        raise ValueError(f"未找到模型 {model} 的 API Key，请在 Agent 页面配置")


def _usage_cb(model: str, purpose: str = "chat"):
    """用量统计回调（惰性 import：usage 依赖 rag.contextvar，无循环）。
    绑定 model/purpose——流式链路 invocation_params 拿不到模型名，构造时兜底。"""
    from yuanai_core.usage import get_usage_handler
    return get_usage_handler(model, purpose)


def get_langgraph_agent(llm, tools):
    return create_react_agent(llm, tools)


def ai_with_tools(question: str):
    llm = get_llm('deepseek-flash', temperature=1, verbose=False)
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
