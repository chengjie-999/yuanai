"""会话标题 AI 生成 — 豆包 lite 后台异步，一次一会话（企业方案对齐：短标题列表）

触发（/chat/save 后 fire-and-forget）：
- 会话 ≥2 条消息 且 当前标题仍是自动标题（「新对话」或首条消息截断式）
- 单次 LLM 调用（不重试，失败下次 save 再试）；in-flight 防重
- 成功 → 更新 ChatSession.title + 清会话缓存（列表立即刷新）
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1)
_inflight: set = set()
_inflight_lock = threading.Lock()

TITLE_PROMPT = ("你是会话标题生成器。根据对话内容生成一个标题："
                "不超过 15 个字，准确概括主题，直接输出标题本身，"
                "不要引号、标点、前缀或任何解释。若无法概括，输出「闲聊」。")


def _is_auto_title(title: str, first_msg: str) -> bool:
    """判断当前标题是否自动生成（默认值或首条消息截断式）。
    C 修复：兼容前端 50 字与后端 80 字两种截断口径（前端写 50、后端判 80
    曾致首条 >50 字时 AI 标题永不生成）。"""
    t = (title or "").strip()
    if not t or t == "新对话":
        return True
    for cut in (50, 80):
        if t == first_msg[:cut] + ("..." if len(first_msg) > cut else ""):
            return True
    return False


def generate_title(session_id: str, messages: list) -> bool:
    """同步执行体（可测试）：从对话生成标题并落库。返回是否更新。"""
    if len(messages) < 2:
        return False
    # 剥 META 信封前缀（防 \x00META\x00 乱码进标题提示词）
    from yuanai_core.core.message import strip as _strip
    first_msg = _strip(messages[0].get("content") or "").strip()
    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user" and _strip(m.get("content") or "").strip():
            last_user = _strip(m["content"]).strip()
            break

    from db.session import get_db, ChatSession
    db = get_db()
    sess = db.Session()
    try:
        row = sess.query(ChatSession).filter_by(session_id=session_id).first()
        if not row or not _is_auto_title(row.title, first_msg):
            return False
        # 已生成过且标题已非自动 → 跳过（上面的判断已覆盖；此处双保险）
        from config.settings import MEMORY_MODEL
        from yuanai_core.core.lc import get_llm
        llm = get_llm(MEMORY_MODEL, reasoning=False, temperature=0.3, timeout=10)
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            future = pool.submit(llm.invoke, [
                ("system", TITLE_PROMPT),
                ("user", f"第一条消息：{first_msg[:200]}\n\n最近一条用户消息：{last_user[:200]}"),
            ])
            resp = future.result(timeout=10)
            title = (resp.content if hasattr(resp, "content") else str(resp)).strip()
        finally:
            pool.shutdown(wait=False)
        title = title.replace("「", "").replace("」", "").replace('"', "").replace("'", "")[:30]
        if not title or title == "闲聊":
            return False
        row.title = title
        sess.commit()
        try:
            from db.cache import clear_chat_cache
            clear_chat_cache(session_id)
        except Exception:
            pass
        logger.info("会话标题生成: %s → %s", session_id[:8], title)
        return True
    except Exception:
        logger.warning("标题生成失败: sid=%s", session_id, exc_info=True)
        return False
    finally:
        sess.close()


def maybe_generate_title(session_id: str, messages: list) -> bool:
    """fire-and-forget 调度（/chat/save 调用；异常全吞）"""
    try:
        if not session_id or len(messages) < 2:
            return False
        with _inflight_lock:
            if session_id in _inflight:
                return False
            _inflight.add(session_id)
        try:
            _executor.submit(_guarded, session_id, messages)
            return True
        except Exception:
            with _inflight_lock:
                _inflight.discard(session_id)
            return False
    except Exception:
        return False


def _guarded(session_id: str, messages: list) -> None:
    try:
        generate_title(session_id, messages)
    except Exception:
        logger.exception("标题生成后台异常: sid=%s", session_id)
    finally:
        with _inflight_lock:
            _inflight.discard(session_id)
