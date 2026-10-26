"""记忆文件存储 — data/.yuan/{user_id}/facts.jsonl（B2 企业级单文件方案，2026-10-26）

写入口只有云端进程（折叠 worker / API 端点）；本地 Agent 的记忆工具经
`/api/v1/agent/memory` HTTP 读写。users.memory 旧字段废弃，懒迁移在 db 层完成。

结构（v2 单文件 JSONL）：
    data/.yuan/{user_id}/facts.jsonl   # 每条一行 JSON：
        {"text": "…", "created_at": "2026-10-11T12:00:00.000000",
         "type": "chat", "source": "fold"}
    每行 json.dumps(ensure_ascii=False)——换行/引号自动转义，正文单行语义不变；
    文件可直接 grep/tail 排查。

v1 旧形态（每条一个 fact-*.md + MEMORY.md 索引）在首次读取时**懒迁移**：
读旧条目 → 写 facts.jsonl → 删除旧 .md 与索引（facts.jsonl 成为唯一真相）。
迁移在调用方持有的 per-user 锁内执行（load_entries 自身不加锁）。

顺序语义：created_at 升序 = 「最旧在前」，超限丢最旧从头部丢。
并发：per-user threading.Lock + 单文件原子替换（tmp 文件 + os.replace——
比 v1 整目录替换更简单更稳）。
"""
import json
import os
import re
import shutil
import threading
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from utils.data_path import root_path

MEMORY_FILE = "facts.jsonl"
MEMORY_INDEX = "MEMORY.md"          # 仅 v1 旧形态识别/迁移用
_FACT_RE = re.compile(r"^fact-(.+)-([0-9a-f]{8})\.md$")
_LOCKS: dict = {}
_LOCKS_GUARD = threading.Lock()


def _now() -> str:
    # 微秒精度：同批写入时排序稳定（created_at 是「丢最旧」的顺序键）
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")


def _mem_dir(user_id) -> str:
    return os.path.join(root_path(), "data", ".yuan", str(user_id))


def _lock_for(user_id) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(str(user_id), threading.Lock())


# ==================== v2 JSONL 读写 ====================

def _read_jsonl(path: str) -> List[dict]:
    """读 facts.jsonl → 条目列表（坏行跳过，不因单行损坏丢掉全部记忆）"""
    entries = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue  # 半行写坏（进程被杀窗口极小）：跳过该行
                if isinstance(obj, dict) and str(obj.get("text", "")).strip():
                    entries.append({"text": str(obj["text"]).strip(),
                                    "created_at": obj.get("created_at", ""),
                                    "type": obj.get("type", "chat"),
                                    "source": obj.get("source", ""),
                                    "file": ""})
    except OSError:
        pass
    return entries


def _write_jsonl(user_id: int, entries: List[dict]) -> None:
    """单文件原子重写：tmp 文件 + os.replace；created_at 空则 base+微秒递增
    补全保证严格单调（排序「丢最旧」的顺序键不能依赖写入顺序）。"""
    d = _mem_dir(user_id)
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f".facts-{uuid.uuid4().hex[:8]}.tmp")
    base = datetime.now()
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            for i, e in enumerate(entries):
                if not e.get("created_at"):
                    e["created_at"] = (base + timedelta(microseconds=i)).strftime("%Y-%m-%dT%H:%M:%S.%f")
                obj = {"text": str(e.get("text", "")).strip(),
                       "created_at": e["created_at"],
                       "type": e.get("type", "chat"),
                       "source": e.get("source", "")}
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        os.replace(tmp, os.path.join(d, MEMORY_FILE))
    finally:
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ==================== v1 旧形态读取与懒迁移 ====================

def _parse_frontmatter(raw: str) -> dict:
    """自实现扁平 frontmatter 解析：--- 开头块，键值标量"""
    meta = {}
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            block = raw[3:end]
            for ln in block.splitlines():
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    meta[k.strip()] = v.strip()
    return meta


def _read_legacy_fact_file(path: str) -> Optional[dict]:
    """v1 单条记忆文件 → {text, created_at, type, source}；解析失败返回 None"""
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return None
    meta = _parse_frontmatter(raw)
    end = raw.find("\n---", 3)
    body = raw[end + 4:].strip() if end != -1 else raw.strip()
    if not body:
        return None
    return {"text": body, "created_at": meta.get("created_at", ""),
            "type": meta.get("type", "chat"), "source": meta.get("source", ""),
            "file": ""}


def _read_legacy_dir(d: str) -> List[dict]:
    entries = []
    try:
        names = os.listdir(d)
    except OSError:
        return entries
    for name in names:
        if name == MEMORY_INDEX or not name.endswith(".md"):
            continue
        e = _read_legacy_fact_file(os.path.join(d, name))
        if e:
            entries.append(e)
    return entries


def _migrate_legacy(user_id: int, d: str, entries: List[dict]) -> None:
    """v1 → v2 懒迁移：旧 .md 条目写 facts.jsonl 后删除旧文件（唯一真相切换）"""
    _write_jsonl(user_id, entries)
    try:
        for name in os.listdir(d):
            if name == MEMORY_FILE:
                continue
            p = os.path.join(d, name)
            try:
                if os.path.isfile(p):
                    os.remove(p)
            except OSError:
                pass
    except OSError:
        pass


def load_entries(user_id) -> List[dict]:
    """读全部记忆条目（created_at 升序 = 最旧在前）；目录不存在返回 []。
    v1 旧 .md 目录首次读取时懒迁移到 facts.jsonl。"""
    d = _mem_dir(user_id)
    if not os.path.isdir(d):
        return []
    jf = os.path.join(d, MEMORY_FILE)
    if os.path.isfile(jf):
        entries = _read_jsonl(jf)
        entries.sort(key=lambda e: e["created_at"] or "")
        return entries
    # v1 旧形态：读旧条目并迁移（调用方多已持有 per-user 锁；裸调用并发迁移幂等）
    entries = _read_legacy_dir(d)
    entries.sort(key=lambda e: e["created_at"] or "")
    if entries:
        _migrate_legacy(user_id, d, entries)
    return entries


def load_facts(user_id) -> List[str]:
    """事实行列表（注入/展示用），最旧在前"""
    with _lock_for(user_id):
        return [e["text"] for e in load_entries(user_id)]


def rewrite(user_id, lines: List[str], source: str = "edit") -> dict:
    """全量覆盖（设置页 PUT）：与旧条目等键/包含的行复用 created_at，其余记当前时间

    返回 {"memory": str, "total": int}
    """
    from yuanai_core.memory import dedup_key
    with _lock_for(user_id):
        old = load_entries(user_id)
        old_keys = [(dedup_key(e["text"]), e) for e in old]
        entries = []
        for ln in lines:
            ln = (ln or "").strip()
            if not ln:
                continue
            key = dedup_key(ln)
            reused = None
            for ok, e in old_keys:
                if key == ok or key in ok or ok in key:
                    reused = e
                    break
            entries.append({"text": ln, "created_at": reused["created_at"] if reused else "",
                            "type": reused["type"] if reused else "chat",
                            "source": reused["source"] if reused else source,
                            "file": ""})
        _write_jsonl(user_id, entries)
        return {"memory": "\n".join(e["text"] for e in entries), "total": len(entries)}


def apply_entries(user_id, entries: List[dict]) -> int:
    """按给定条目全量重写（自整理用；条目形状同 load_entries 输出，
    created_at 空则记当前时间）。返回条目总数。"""
    with _lock_for(user_id):
        clean = [e for e in entries if str(e.get("text", "")).strip()]
        _write_jsonl(user_id, clean)
        return len(clean)


def add_facts(user_id, new_lines: List[str], max_items: int = 100,
              max_chars: int = 2000, source: str = "fold") -> dict:
    """合并新事实（只追加 + 双向去重 + 超限丢最旧，逻辑复用 yuanai_core.memory.merge_facts）

    返回 {"added": int, "total": int}
    """
    from yuanai_core.memory import merge_facts, dedup_key, _is_placeholder
    with _lock_for(user_id):
        old = load_entries(user_id)
        clean_lines = [ln.strip() for ln in new_lines
                       if ln.strip() and not _is_placeholder(ln)]
        merged, added = merge_facts([e["text"] for e in old], clean_lines,
                                    max_items, max_chars)
        old_map = {}
        for e in old:
            old_map.setdefault(dedup_key(e["text"]), e)
        entries = []
        for ln in merged:
            key = dedup_key(ln)
            reused = None
            if key in old_map:
                reused = old_map[key]
            else:
                for ok, e in old_map.items():
                    if ok in key or key in ok:
                        reused = e
                        break
            entries.append({"text": ln, "created_at": reused["created_at"] if reused else "",
                            "type": reused["type"] if reused else "chat",
                            "source": reused["source"] if reused else source,
                            "file": ""})
        _write_jsonl(user_id, entries)
        return {"added": added, "total": len(entries)}


def delete_fact(user_id, keyword: str) -> dict:
    """按文本删除：先精确匹配（strip 相等），无命中再唯一子串匹配。

    返回 {"deleted": n, "total": m, "memory": str, "asked_more": bool}
    """
    kw = (keyword or "").strip()
    with _lock_for(user_id):
        old = load_entries(user_id)
        if not old or not kw:
            return {"deleted": 0, "total": len(old),
                    "memory": "\n".join(e["text"] for e in old), "asked_more": False}
        # 精确匹配
        hits = [e for e in old if e["text"].strip() == kw]
        if not hits:
            hits = [e for e in old if kw in e["text"]]
        if len(hits) > 1:
            return {"deleted": 0, "total": len(old),
                    "memory": "\n".join(e["text"] for e in old), "asked_more": True}
        if not hits:
            return {"deleted": 0, "total": len(old),
                    "memory": "\n".join(e["text"] for e in old), "asked_more": False}
        remaining = [e for e in old if e is not hits[0]]
        _write_jsonl(user_id, remaining)
        return {"deleted": 1, "total": len(remaining),
                "memory": "\n".join(e["text"] for e in remaining), "asked_more": False}


def clear(user_id) -> None:
    """清空该用户全部记忆"""
    with _lock_for(user_id):
        d = _mem_dir(user_id)
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
