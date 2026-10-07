"""Token 用量统计 — 支付与金融分析的账本地基（单一挂点，零改调用方）

设计：
- lc.get_llm 在 LLM 构造器上挂 UsageTrackingHandler（LangChain 回调），
  每次 invoke/stream 结束自动上报 usage（云/边双端都走这个工厂）
- 用户归属：current_user_id contextvar（云端 chat/stream 与 Agent ws_client
  均已设置；未设置记 0 = 系统/后台任务）
- 缓冲 + 单 worker 异步落库：统计绝不阻塞对话主流程，异常全吞
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from langchain_core.callbacks import BaseCallbackHandler

from yuanai_core.rag import current_user_id

logger = logging.getLogger(__name__)

MAX_BUFFER = 50
FLUSH_INTERVAL_S = 10

_buffer: list = []
_buffer_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1)


def record_usage(user_id: int, model: str, purpose: str,
                 prompt_tokens: int, completion_tokens: int,
                 source: str = "cloud") -> None:
    """入缓冲；满 50 条或超 10 秒由后台线程批量落库"""
    if not prompt_tokens and not completion_tokens:
        return  # 无用量数据（如旧模型响应缺 usage）不记账
    with _buffer_lock:
        _buffer.append({
            "user_id": user_id or 0, "model": model, "purpose": purpose,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens, "source": source,
        })
        if len(_buffer) >= MAX_BUFFER:
            rows, _buffer[:] = _buffer, []
            _submit_flush(rows)
        else:
            _maybe_interval_flush()


def _maybe_interval_flush() -> None:
    if _buffer and time.time() - _last_flush_time > FLUSH_INTERVAL_S:
        _last_flush_time = time.time()
        rows, _buffer[:] = _buffer, []
        _submit_flush(rows)


_last_flush_time = time.time()


def model_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """单次调用成本（元）：模型定价 × token 数；未定价模型返回 0"""
    from config.settings import MODEL_PRICING
    price = MODEL_PRICING.get(model or "")
    if not price:
        return 0.0
    return round(prompt_tokens / 1_000_000 * price.get("in", 0)
                 + completion_tokens / 1_000_000 * price.get("out", 0), 6)


def _submit_flush(rows: list) -> None:
    try:
        _executor.submit(_flush_rows, rows)
    except Exception:
        logger.warning("usage 落库提交失败（数据丢弃 %d 条）", len(rows))


def _flush_rows(rows: list) -> None:
    try:
        from db.session import get_db
        get_db().add_token_usage_rows(rows)
    except Exception as e:
        logger.warning("usage 落库失败: %s", e)


def flush_now() -> None:
    """立即冲刷缓冲（进程退出/测试用）"""
    with _buffer_lock:
        rows, _buffer[:] = _buffer, []
    if rows:
        _flush_rows(rows)


class UsageTrackingHandler(BaseCallbackHandler):
    """LangChain 回调：on_llm_end 提取 token 用量并记账。

    由 lc.get_llm 挂在每个 LLM 实例上；provider 无关（langchain_openai
    对 DeepSeek/豆包都把用量放 response.usage_metadata / response_metadata）。
    """

    def on_llm_end(self, response, **kwargs) -> None:
        try:
            usage = getattr(response, "usage_metadata", None) or {}
            if not usage:
                usage = (getattr(response, "response_metadata", None) or {}).get("token_usage") or {}
            prompt_tokens = int(usage.get("input_tokens") or 0)
            completion_tokens = int(usage.get("output_tokens") or 0)
            if not prompt_tokens and not completion_tokens:
                return
            model = ""
            params = kwargs.get("invocation_params") or {}
            if isinstance(params, dict):
                model = str(params.get("model", "") or params.get("model_name", ""))
            user_id = current_user_id.get() or 0
            source = "agent" if user_id and user_id < 0 else ("cloud" if user_id else "cloud")
            record_usage(user_id, model, "chat", prompt_tokens, completion_tokens,
                         source="cloud")
        except Exception:
            # 统计回调绝不抛出（langchain 会吞，但双保险）
            pass


_handler = UsageTrackingHandler()


def get_usage_handler() -> UsageTrackingHandler:
    """lc.py 挂载用单例（回调本身无状态，线程安全）"""
    return _handler
