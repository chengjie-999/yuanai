# -*- coding: utf-8 -*-
"""用户 Agent LLM 云端代理（T5，2026-11-06）——用户 Agent 可用的前置条件

普通用户本机没有 API key：本地 Agent 的 LLM 调用把 base_url 指向本端点、
api_key 用 agent_secret，云端用自己的 DeepSeek/豆包 key 转发（OpenAI 兼容
格式，流式透传），统一记账与限额收口云端。

- 鉴权：X-Agent-Id + X-Agent-Secret 设备凭据（与 planet/plan 同步同链）
- 绑定：agent_devices 一对一绑定 → user_id（未绑定 403）
- 欠费：显示金额 ≤ -ARREARS_LIMIT → 403（与 /chat/stream 同口径）
- 模型白名单：仅 models.json 登记模型（防滥用任意模型名/端点）
- 记账：强制 include_usage 取 token 数 → record_usage(purpose=agent_llm，
  成本落绑定用户 → 盈利系数/成本分析/欠费全链路生效）；Agent 端走代理时
  不挂本地记账回调（防双计）
- 高并发收口：全局限流中间件对 /api/ 生效；DeepSeek/豆包账号级速率限制
  由上游返回 429 透传（排队策略挂账）
"""
import json
import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.v1.agent.router import require_agent_uid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent/llm", tags=["agent-llm"])

_TIMEOUT = httpx.Timeout(connect=10, read=300, write=60, pool=10)


def _provider_endpoint(model: str) -> tuple:
    """模型 → (转发端点, key)。key 与 lc.get_llm 同源（models.json _apikeys → env）"""
    from yuanai_core.core.lc import _get_stored_key, dsllm, seed
    from utils.sensitive_data import get_api_key
    if model in dsllm:
        key = _get_stored_key("DeepSeek") or get_api_key('dsllm')
        return ("https://api.deepseek.com/beta", key)
    if model in seed:
        key = _get_stored_key("Doubao") or get_api_key('seed')
        return ("https://ark.cn-beijing.volces.com/api/v3", key)
    return ("", "")


def _model_allowed(model: str) -> bool:
    """模型白名单：resolve 后必须 ∈ 云端登记模型（MODELS 或 Agent 分配表）"""
    from yuanai_core.core.lc import resolve_model_id
    try:
        resolved = resolve_model_id(model)
    except Exception:
        return False
    from config.settings import MODELS, AGENT_MODEL_MAP
    allowed = set(MODELS.keys())
    allowed.update(str(v) for v in (AGENT_MODEL_MAP or {}).values() if v)
    return resolved in allowed or model in allowed


def _check_arrears(uid: int) -> None:
    """欠费拦截（与 /chat/stream 同口径；异常静默放行）"""
    from api.v1.chat.router import _check_arrears
    msg = _check_arrears(uid)
    if msg:
        raise HTTPException(status_code=403, detail=msg)


@router.post("/chat/completions")
async def chat_completions(request: Request):
    """OpenAI 兼容 Chat Completions 代理（ChatOpenAI base_url 指向本端点）"""
    uid = require_agent_uid(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体需为 JSON")
    model = str(body.get("model", ""))
    if not model:
        raise HTTPException(status_code=400, detail="缺少 model 字段")
    if not _model_allowed(model):
        raise HTTPException(status_code=403, detail=f"模型 {model} 未在平台登记（模型白名单）")
    _check_arrears(uid)
    endpoint, api_key = _provider_endpoint(model)
    if not endpoint or not api_key:
        raise HTTPException(status_code=502, detail="平台未配置该模型通道的 API Key")

    # 强制 include_usage：流式响应才带 usage，否则云端记账拿不到 token 数
    body["stream_options"] = {"include_usage": True}
    stream = bool(body.get("stream"))

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = endpoint.rstrip("/") + "/chat/completions"
    client = httpx.AsyncClient(timeout=_TIMEOUT)

    async def _forward_stream():
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "cache_hit": 0}
        try:
            async with client.stream("POST", url, json=body, headers=headers) as resp:
                if resp.status_code != 200:
                    # SSE 已开流改不了状态码——产出 OpenAI 错误格式的 data 行，
                    # 客户端（ChatOpenAI）会解析出上游错误并抛异常
                    err_body = (await resp.aread()).decode("utf-8", errors="replace")
                    logger.error("LLM 代理上游错误(流): status=%s model=%s", resp.status_code, model)
                    yield f'data: {{"error": {{"message": "upstream {resp.status_code}", "type": "upstream_error"}}}}\n\n'.encode()
                    yield b"data: [DONE]\n\n"
                    return
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        try:
                            chunk = json.loads(line[5:].strip())
                            if isinstance(chunk, dict):
                                u = chunk.get("usage")
                                if isinstance(u, dict):
                                    usage["prompt_tokens"] = int(u.get("prompt_tokens") or 0)
                                    usage["completion_tokens"] = int(u.get("completion_tokens") or 0)
                                    if u.get("prompt_cache_hit_tokens") is not None:
                                        usage["cache_hit"] = int(u["prompt_cache_hit_tokens"])
                        except Exception:
                            pass
                    yield (line + "\n").encode("utf-8")
        finally:
            _record(uid, model, usage)
            await client.aclose()

    async def _forward_full():
        try:
            resp = await client.post(url, json=body, headers=headers)
            if resp.status_code != 200:
                raise _UpstreamError(resp.status_code, resp.text)
            data = resp.json()
            u = data.get("usage") or {}
            _record(uid, model, {
                "prompt_tokens": int(u.get("prompt_tokens") or 0),
                "completion_tokens": int(u.get("completion_tokens") or 0),
                "cache_hit": int(u.get("prompt_cache_hit_tokens") or 0),
            })
            return data
        finally:
            await client.aclose()

    if stream:
        return StreamingResponse(_forward_stream(), media_type="text/event-stream")
    try:
        return await _forward_full()
    except _UpstreamError as e:
        logger.error("LLM 代理上游错误: status=%s model=%s", e.status, model)
        raise HTTPException(status_code=502, detail=f"上游模型服务错误（{e.status}）")


class _UpstreamError(Exception):
    def __init__(self, status: int, body: str = ""):
        self.status = status
        self.body = body
        super().__init__(f"upstream {status}")


def _record(uid: int, model: str, usage: dict) -> None:
    """统一记账（T5）：usage_purpose=agent_llm，成本落绑定用户；零 token 不记"""
    pt, ct = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    if not pt and not ct:
        return
    try:
        from yuanai_core.usage import record_usage
        record_usage(uid, model, "agent_llm", pt, ct,
                     source="cloud", cache_hit_tokens=usage.get("cache_hit", 0))
    except Exception as e:
        logger.warning("LLM 代理记账失败: %s", e)
