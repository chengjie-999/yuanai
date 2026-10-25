"""记忆定期自动整理 — /chat/save 后 fire-and-forget 触发（系统任务，2026-10-25）

与 organize_user_memory 工具的分工：
- 工具 = 模型对话中自发调用（受会话护栏：只删本会话内新增 + 每日 3 条）
- 本模块 = **系统节流调度**（每用户每 N 小时一次）：把当前记忆清单交给豆包 lite
  重写为「整理后清单」——合并重复、清理过时、补充事实——差异推断（plan_organize）
  后原子写回。模型无需自发调用，记忆始终保持整洁。

护栏（系统任务自己的口径）：
- 触发：记忆条目数 ≥ MEMORY_ORGANIZE_AUTO_MIN_ITEMS 且距上次 ≥ 间隔（Redis TTL）
- 单次删除上限 MEMORY_ORGANIZE_AUTO_DELETE_MAX（超出部分保留不删——防模型误删兜底）
- 每次删除写审计日志 data/logs/memory_audit.log（source=auto_organize）
- 失败/空输出静默跳过（下次 save 自然重试）；Redis 故障跳过（烧钱保守）
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# 模块级单 worker（照 memory_fold 模式）；后台任务绝不抛异常给解释器
_executor = ThreadPoolExecutor(max_workers=1)
_inflight: set = set()
_inflight_lock = threading.Lock()


def _interval_elapsed(user_id: int, hours: int) -> bool:
    """Redis TTL 节流：SETNX 成功 = 本轮执行并占位 hours；键已存在 = 间隔未到。
    Redis 故障 → False（跳过本轮，烧钱保守）"""
    try:
        from db.redis_client import get_redis
        rds = get_redis()
        return bool(rds.set(f"mem_org_auto:{user_id}", "1", ex=hours * 3600, nx=True))
    except Exception:
        logger.warning("自动整理节流检查失败（跳过本轮）: uid=%s", user_id, exc_info=True)
        return False


def maybe_schedule_memory_organize(user_id: int) -> bool:
    """请求内零成本预筛：开关 + Redis 间隔 + in-flight 防重；异常全吞，
    绝不拖慢 /chat/save 响应。返回是否已调度。"""
    try:
        from config.settings import (MEMORY_ENABLED, MEMORY_ORGANIZE_AUTO_ENABLED,
                                     MEMORY_ORGANIZE_AUTO_INTERVAL_HOURS)
        if not MEMORY_ENABLED or not MEMORY_ORGANIZE_AUTO_ENABLED or not user_id:
            return False
        if not _interval_elapsed(user_id, MEMORY_ORGANIZE_AUTO_INTERVAL_HOURS):
            return False
        with _inflight_lock:
            if user_id in _inflight:
                return False
            _inflight.add(user_id)
        try:
            _executor.submit(_guarded, user_id)
            return True
        except Exception as e:
            logger.warning("自动整理任务提交失败: %s", e)
            with _inflight_lock:
                _inflight.discard(user_id)
            return False
    except Exception:
        return False


def _audit_auto_organize(user_id: int, texts: list) -> None:
    """自动整理删除审计（与 db._audit_organize 同文件同格式，source 区分）"""
    import json
    import os
    from datetime import datetime
    from utils.data_path import root_path
    try:
        path = os.path.join(root_path(), "data", "logs", "memory_audit.log")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        line = (f"{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} uid={user_id} "
                f"sid= source=auto_organize deleted={json.dumps(texts, ensure_ascii=False)}\n")
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def run_memory_organize(user_id: int) -> dict:
    """工作线程执行体（同步，零 DB 依赖，可测试）。
    返回 {"organized": True, "deleted": n, "total": m} 或 {"skipped": reason}"""
    from config.settings import (MEMORY_ORGANIZE_AUTO_MIN_ITEMS,
                                 MEMORY_ORGANIZE_AUTO_DELETE_MAX,
                                 MEMORY_MAX_ITEMS, MEMORY_MAX_CHARS)
    from yuanai_core import memory_store
    from yuanai_core.memory import plan_organize, _call_fold_llm

    old = memory_store.load_entries(user_id)
    lines = [e["text"] for e in old if str(e.get("text", "")).strip()]
    if len(lines) < MEMORY_ORGANIZE_AUTO_MIN_ITEMS:
        return {"skipped": "below_min_items"}

    # 清单给模型：明确「输出中未出现的旧行将被删除」的语义——仍有效的必须保留
    numbered = "\n".join(f"{i + 1}. {ln}" for i, ln in enumerate(lines))
    system = (
        "你是用户长期记忆的整理员。请对下面的记忆清单做三件事："
        "① 合并重复或同义的条目 ② 删除过时、矛盾或不再成立的条目 ③ 把不完整的条目改写完整。"
        "输出整理后的完整清单，每行一条记忆，只输出清单本身，不要编号不要解释。"
        "注意：输出清单中未包含的旧条目会被视为删除——凡是仍然有效的记忆必须原样或改写后保留。"
    )
    try:
        out = _call_fold_llm(system, numbered)
    except Exception as e:
        logger.warning("自动整理 LLM 调用失败（跳过本轮）: uid=%s err=%s", user_id, str(e)[:120])
        return {"skipped": "llm_error"}
    if not out or not out.strip():
        return {"skipped": "llm_empty"}

    plan = plan_organize(old, [ln.strip() for ln in out.splitlines()])
    deletions = plan["deletions"]
    kept = plan["kept"]

    # 单次删除上限：超出部分保留（不删）——模型误删兜底
    if len(deletions) > MEMORY_ORGANIZE_AUTO_DELETE_MAX:
        overflow = deletions[MEMORY_ORGANIZE_AUTO_DELETE_MAX:]
        deletions = deletions[:MEMORY_ORGANIZE_AUTO_DELETE_MAX]
        kept = overflow + kept

    # 上限兜底（同 organize_user_memory：超限丢最旧）
    while len(kept) > MEMORY_MAX_ITEMS:
        kept.pop(0)
    while len(kept) > 1 and sum(len(e["text"]) for e in kept) + len(kept) > MEMORY_MAX_CHARS:
        kept.pop(0)

    total = memory_store.apply_entries(user_id, kept)
    if deletions:
        _audit_auto_organize(user_id, [d["text"] for d in deletions])
    logger.info("记忆自动整理完成: uid=%s deleted=%d total=%d", user_id, len(deletions), total)
    return {"organized": True, "deleted": len(deletions), "total": total}


def _guarded(user_id: int) -> None:
    """后台任务壳：异常吞掉并摘除 in-flight"""
    try:
        run_memory_organize(user_id)
    except Exception:
        logger.exception("记忆自动整理后台任务异常: uid=%s", user_id)
    finally:
        with _inflight_lock:
            _inflight.discard(user_id)
