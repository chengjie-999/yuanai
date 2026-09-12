TOOL_CATEGORY = "knowledge"

"""知识星球检索工具 — 只读：检索用户个人的思维导图与线性笔记，不提供任何写回。

被 tools/__init__.py 的 load_all_tools 自动发现（TOOL_CATEGORY="knowledge"），
云端回退链路（api/v1/chat/router.py all_tools）与本机 orchestrator 自动获得。
"""
import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# 星球名 → 该用户 source 列表的进程内缓存（检索频繁，避免每次打 MySQL）
_planet_cache: dict[int, dict] = {}  # uid -> {"name_to_sources": {...}, "ts": float}
_CACHE_TTL = 60


@tool
def retrieve_planet_knowledge(query: str, planet: str = "") -> str:
    """Search user's personal knowledge planet (mind maps & linear notes, read-only).
    query: keywords to search for. planet: optional planet name to restrict search."""
    try:
        from yuanai_core.rag import search_knowledge_hits, current_user_id
        from db.session import get_db

        try:
            uid = current_user_id.get()
        except Exception:
            uid = 0
        if not uid:
            return "未登录，无法检索个人知识星球"

        if not query.strip():
            return "请提供搜索关键词"

        # 该用户的全部星球 source（导图节点 + 笔记分块）
        sources, names = _user_planet_sources(uid)
        if not sources:
            return "你的知识星球还是空的（在 /chat/planet 导入导图或笔记后即可检索）"
        if planet:
            matched = [p for p in names if planet in p["name"]]
            if not matched:
                return f"没有名为「{planet}」的星球。现有星球: {', '.join(n['name'] for n in names)}"
            pid = matched[0]["id"]
            prefix = f"planet:{uid}:{pid}:"
            sources = [s for s in sources if s.startswith(prefix)]

        hits = search_knowledge_hits(query, top_k=5, sources=sources, user_id=uid, fallback=False)
        if not hits:
            return f"知识星球中没有找到与 '{query}' 相关的内容"
        return _format_hits(hits)
    except Exception as e:
        logger.error("知识星球检索失败: %s", e, exc_info=True)
        return f"知识星球检索暂时不可用: {e}"


def _user_planet_sources(uid: int) -> tuple[list, list]:
    """用户的全部星球 source 列表 + [{id,name}]（60s 缓存）"""
    import time

    cached = _planet_cache.get(uid)
    if cached and time.time() - cached["ts"] < _CACHE_TTL:
        return cached["sources"], cached["names"]

    db = get_db()
    names = [{"id": p["id"], "name": p["name"]} for p in db.list_planets(uid)]
    sources = []
    for p in names:
        sources.append(f"planet:{uid}:{p['id']}:")
        for m in db.list_maps(p["id"], user_id=uid):
            sources.append(f"planet:{uid}:{p['id']}:{m['id']}")
            sources.append(f"planet:{uid}:{p['id']}:{m['id']}:note")
    _planet_cache[uid] = {"sources": sources, "names": names, "ts": time.time()}
    return sources, names


def _format_hits(hits: list[dict]) -> str:
    """结构化命中 → 字符串（[星球/导图] 路径 + 正文）"""
    chunks = []
    for h in hits:
        src = h["source"]
        try:
            _p, uid, pid, mid, *rest = src.split(":")
        except ValueError:
            label = src
        else:
            label = f"星球#{pid}/导图#{mid}" + ("/笔记" if rest else "")
        header = f"[{label}] {h['path'] or h['title']}"
        chunks.append(header + "\n" + h["text"])
        for img in h["images"]:
            chunks.append(f"  ![图片]({img})")
    return "\n---\n".join(chunks)
