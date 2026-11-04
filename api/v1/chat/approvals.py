# -*- coding: utf-8 -*-
"""云端直连审批决议注册表（V1-2 审批分层）

SSE 流执行到 L2 工具时暂停，等待用户在气泡审批卡上点「允许/拒绝」——
决议经新的 POST /chat/stream（body.decision）到达，本模块按 decision_id 配对：
- await_decision：流侧注册 Future 并等待（超时默认 None → deny，fail-closed）
- resolve_decision：决议请求侧置结果；未知 id 返回 False（迟到/伪造一律无效）

进程内单事件循环（uvicorn 全请求同 loop），模块级 dict 安全。
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

# decision_id → asyncio.Future（值为 "approve" / "deny"）
_PENDING: dict = {}

# 审批等待上限（秒）：与前端 ApprovalCard timeoutSeconds 一致
APPROVAL_TIMEOUT = 120


async def await_decision(decision_id: str, timeout: int = APPROVAL_TIMEOUT):
    """注册并等待决议。返回 "approve" / "deny" / None（超时或异常）。"""
    fut = asyncio.get_running_loop().create_future()
    _PENDING[decision_id] = fut
    try:
        return await asyncio.wait_for(asyncio.shield(fut), timeout)
    except asyncio.TimeoutError:
        return None
    except Exception:
        return None
    finally:
        _PENDING.pop(decision_id, None)
        if not fut.done():
            fut.cancel()


def resolve_decision(decision_id: str, approve: bool) -> bool:
    """决议请求侧：置结果。找到未决 Future → True；未知/已决 → False。"""
    fut = _PENDING.get(decision_id)
    if fut and not fut.done():
        fut.set_result("approve" if approve else "deny")
        return True
    return False


def pending_count() -> int:
    """当前挂起的审批数（观测/测试用）"""
    return len(_PENDING)
