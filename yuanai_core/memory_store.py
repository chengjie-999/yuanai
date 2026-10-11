"""记忆文件存储 — data/.yuan/{user_id}/（Claude Code 记忆目录风格，用户拍板）

写入口只有云端进程（折叠 worker / API 端点）；本地 Agent 的记忆工具经
`/api/v1/agent/memory` HTTP 读写。users.memory 旧字段废弃，懒迁移在 db 层完成。

结构：
    data/.yuan/{user_id}/
    ├── MEMORY.md                      # 索引（- [摘要](file.md) — created_at）
    └── fact-{slug}-{uuid8}.md         # 每条记忆一个文件：
        ---                            #   自实现扁平 frontmatter（不引 PyYAML，
        name: 前 20 字                  #   同 vault_note 惯例）
        description: 正文（单行）
        type: chat
        created_at: 2026-10-11T12:00:00
        source: fold
        ---
        <正文一行>

顺序语义：created_at 升序 = 「最旧在前」，超限丢最旧从头部丢。
并发：per-user threading.Lock + 整目录原子替换（临时目录 + rename）。
"""
import os
import re
import shutil
import threading
import uuid
from datetime import datetime
from typing import List, Optional

from utils.data_path import root_path

MEMORY_INDEX = "MEMORY.md"
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


def _slug(text: str) -> str:
    """文件名安全基（中文保留，非法字符换下划线，最长 16 字）"""
    t = re.sub(r'[\\/:*?"<>|\r\n\t ]+', "-", text.strip())
    t = re.sub(r"-{2,}", "-", t).strip("-")
    return (t or "fact")[:16]


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


def _read_fact_file(path: str) -> Optional[dict]:
    """读单条记忆文件 → {text, created_at, type, source, file}；解析失败返回 None"""
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
            "file": os.path.basename(path)}


def _write_fact_file(dirpath: str, text: str, created_at: str,
                     mtype: str = "chat", source: str = "") -> str:
    """写一条记忆 → 文件名；created_at 空则取当前时间"""
    created_at = created_at or _now()
    fname = f"fact-{_slug(text)}-{uuid.uuid4().hex[:8]}.md"
    name = re.sub(r"\s+", " ", text)[:20]
    desc = re.sub(r"[\r\n]+", " ", text)
    content = (f"---\nname: {name}\ndescription: {desc}\n"
               f"type: {mtype}\ncreated_at: {created_at}\nsource: {source}\n---\n{text}\n")
    with open(os.path.join(dirpath, fname), "w", encoding="utf-8") as f:
        f.write(content)
    return fname


def _write_index(dirpath: str, entries: List[dict]) -> None:
    lines = ["# 小元AI 记忆索引", ""]
    for e in entries:
        lines.append(f"- [{e['text'][:20]}]({e['file']}) — {e['created_at']}")
    with open(os.path.join(dirpath, MEMORY_INDEX), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _atomic_rewrite(user_id: int, entries: List[dict]) -> None:
    """整目录原子替换（临时目录 + rename），entries 按序写入并补齐文件名

    同批新条目的 created_at 用 base+微秒递增保证严格单调——排序（丢最旧
    的顺序键）不能依赖文件系统 listdir 顺序。
    """
    from datetime import datetime, timedelta

    target = _mem_dir(user_id)
    tmp = os.path.join(root_path(), "data", ".yuan", f".tmp-{user_id}-{uuid.uuid4().hex[:8]}")
    os.makedirs(tmp, exist_ok=True)
    base = datetime.now()
    try:
        for i, e in enumerate(entries):
            if not e.get("created_at"):
                e["created_at"] = (base + timedelta(microseconds=i)).strftime("%Y-%m-%dT%H:%M:%S.%f")
            e["file"] = _write_fact_file(tmp, e["text"], e["created_at"],
                                         e.get("type", "chat"), e.get("source", ""))
        _write_index(tmp, entries)
        bak = None
        if os.path.isdir(target):
            bak = target + ".bak"
            if os.path.exists(bak):
                shutil.rmtree(bak, ignore_errors=True)
            os.rename(target, bak)
        os.rename(tmp, target)
        if bak:
            shutil.rmtree(bak, ignore_errors=True)
    finally:
        if os.path.isdir(tmp):
            shutil.rmtree(tmp, ignore_errors=True)


def load_entries(user_id) -> List[dict]:
    """读全部记忆条目（created_at 升序 = 最旧在前）；目录不存在返回 []"""
    d = _mem_dir(user_id)
    if not os.path.isdir(d):
        return []
    entries = []
    for name in os.listdir(d):
        if name == MEMORY_INDEX or not name.endswith(".md"):
            continue
        e = _read_fact_file(os.path.join(d, name))
        if e:
            entries.append(e)
    entries.sort(key=lambda e: e["created_at"] or "")
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
        _atomic_rewrite(user_id, entries)
        return {"memory": "\n".join(e["text"] for e in entries), "total": len(entries)}


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
        _atomic_rewrite(user_id, entries)
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
        _atomic_rewrite(user_id, remaining)
        return {"deleted": 1, "total": len(remaining),
                "memory": "\n".join(e["text"] for e in remaining), "asked_more": False}


def clear(user_id) -> None:
    """清空该用户全部记忆"""
    with _lock_for(user_id):
        d = _mem_dir(user_id)
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
