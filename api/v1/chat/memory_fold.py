"""记忆折叠服务层 — /chat/save 后 fire-and-forget 触发，豆包 lite 后台异步

- maybe_schedule_memory_fold：请求内零成本预筛（条数/字数阈值），异常全吞，
  绝不拖慢 /chat/save 响应
- run_memory_fold：工作线程执行体（同步可测）：重读 DB 消息数组 → 游标 clamp
  → 烧钱护栏 → 每日限额 → 点踩集合 → fold_material → 合并记忆 → 游标前进
- 失败/超时：游标不动，下次 save 自然重试；LLM 空输出 = 遗忘（游标照常前进）
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# 模块级单 worker（照 api/v1/planet/router.py 模式）；后台任务绝不抛异常给解释器
_executor = ThreadPoolExecutor(max_workers=1)
_inflight: set = set()
_inflight_lock = threading.Lock()


def maybe_schedule_memory_fold(session_id: str, user_id: int,
                               msg_count: int = None, total_chars: int = None) -> bool:
    """请求内预筛：开关 + 归属 + 阈值（>20 条或 >8000 字）；通过则入队后台执行。

    msg_count=None（如语音挂点）→ 跳过预筛直接入队，由工作线程 get_session_stats 复检。
    返回是否已调度（供日志/测试断言）。
    """
    try:
        from config.settings import (MEMORY_ENABLED, MEMORY_WORKING_WINDOW,
                                     MEMORY_TRIGGER_CHARS)
        if not MEMORY_ENABLED or not user_id or not session_id:
            return False
        if msg_count is not None:
            if msg_count <= MEMORY_WORKING_WINDOW and (total_chars or 0) <= MEMORY_TRIGGER_CHARS:
                return False
        with _inflight_lock:
            if session_id in _inflight:
                return False
            _inflight.add(session_id)
        try:
            _executor.submit(_guarded, session_id, user_id, msg_count, total_chars)
            return True
        except Exception as e:
            logger.warning("记忆折叠任务提交失败: %s", e)
            with _inflight_lock:
                _inflight.discard(session_id)
            return False
    except Exception:
        # 触发逻辑绝不影响主流程（/chat/save 调用方还会再吞一层）
        return False


def run_memory_fold(session_id: str, user_id: int,
                    msg_count: int = None, total_chars: int = None) -> dict:
    """工作线程执行体（同步，可测试）。返回 {"folded", "facts"} 或 {"skipped", "reason"}。"""
    from config.settings import (MEMORY_WORKING_WINDOW, MEMORY_TRIGGER_CHARS,
                                 MEMORY_FOLD_INPUT_MAX_CHARS, MEMORY_MAX_ITEMS,
                                 MEMORY_MAX_CHARS, MEMORY_FOLD_DAILY_MAX)
    from db.session import get_db
    from yuanai_core.memory import fold_material, should_fold

    db = get_db()

    # 1) 复检（调用方未预筛时）：阈值不满足直接跳过
    if msg_count is None:
        stats = db.get_session_stats(session_id)
        msg_count, total_chars = stats["msg_count"], stats["total_chars"]
    if msg_count <= MEMORY_WORKING_WINDOW and (total_chars or 0) <= MEMORY_TRIGGER_CHARS:
        return {"skipped": "below_threshold"}

    # 2) 读 DB 消息数组（与持久化一致、与反馈下标同一坐标系）
    msgs = db.get_chats(session_id)
    L = len(msgs)
    end = max(0, L - MEMORY_WORKING_WINDOW)
    if end <= 0:
        return {"skipped": "no_material"}

    state = db.get_session_memory_state(session_id)
    folded = max(0, min(state["folded_count"] if state else 0, end))  # 编辑重发回夹
    if folded >= end:
        return {"skipped": "nothing_new"}

    material_count = end - folded
    material_chars = sum(len(m.get("content") or "") for m in msgs[folded:end])

    # 3) 烧钱护栏：材料太少不调 LLM
    if not should_fold(material_count, material_chars):
        return {"skipped": "below_fold_guard"}

    # 4) 每日限额（Redis 计数；Redis 故障宽松放行）
    if MEMORY_FOLD_DAILY_MAX > 0:
        try:
            from api.v1.db_helpers import check_daily_quota
            if not check_daily_quota(f"mem:{user_id}", MEMORY_FOLD_DAILY_MAX):
                return {"skipped": "daily_quota_exceeded"}
        except Exception:
            pass

    # 5) 点踩集合 + 折叠
    fb = db.get_session_feedback(session_id)
    disliked = {i for i, v in fb.items() if v.get("disliked")}
    memory = db.get_user_memory(user_id) or ""
    res = fold_material(memory, msgs, folded, end, disliked)

    if not res["ok"]:
        logger.warning("记忆折叠失败（游标不动，下次重试）: sid=%s reason=%s",
                       session_id, res["reason"])
        return {"skipped": res["reason"]}

    # 6) 合并记忆（空 facts = 遗忘，正常前进游标）+ 游标前进（max 语义防并发回退）
    if res["facts"]:
        db.merge_user_memory(user_id, res["facts"], MEMORY_MAX_ITEMS, MEMORY_MAX_CHARS)
    db.upsert_session_memory_state(session_id, user_id, folded + res["k"])
    logger.info("记忆折叠完成: sid=%s folded=%d facts=%d", session_id, res["k"], len(res["facts"]))
    return {"folded": res["k"], "facts": len(res["facts"])}


def _guarded(session_id: str, user_id: int, msg_count: int, total_chars: int) -> None:
    """后台任务壳：异常吞掉并摘除 in-flight（绝不把异常抛给线程池）"""
    try:
        run_memory_fold(session_id, user_id, msg_count, total_chars)
    except Exception:
        logger.exception("记忆折叠后台任务异常: sid=%s", session_id)
    finally:
        with _inflight_lock:
            _inflight.discard(session_id)
