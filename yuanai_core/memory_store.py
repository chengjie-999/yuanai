"""记忆文件存储 — data/.yuan/{user_id}/facts.jsonl（B2 企业级单文件方案，2026-10-26；
v3 条目事件化 2026-11-06：每个条目有 id/来源/替代链/命中统计/状态，只归档不删除）

写入口只有云端进程（折叠 worker / API 端点）；本地 Agent 的记忆工具经
`/api/v1/agent/memory` HTTP 读写。users.memory 旧字段废弃，懒迁移在 db 层完成。

结构（v3 单文件 JSONL）：
    data/.yuan/{user_id}/facts.jsonl   # 每条一行 JSON：
        {"id": "f_<12hex>", "text": "…",
         "created_at": "2026-10-11T12:00:00.000000",
         "type": "chat", "source": "fold", "session_id": "", "turn": 0,
         "supersedes": "", "superseded_by": "", "superseded_at": "",
         "last_hit": "", "hit_count": 0, "status": "active"}
    每行 json.dumps(ensure_ascii=False)——换行/引号自动转义，正文单行语义不变；
    文件可直接 grep/tail 排查。

v3 语义（V1-3 记忆条目事件化，只归档不删除）：
- id：条目稳定标识（v2 存量行首次读取时懒迁移补发）
- supersedes/superseded_by：双向去重的升级语义升级为显式替代链
  （新行 ⊃ 旧行 → 新行 supersedes 旧行 id，旧行 status=superseded）
- last_hit/hit_count：注入命中统计（mark_hit 更新，供淘汰判定）
- status：active / superseded（被替代，7 天窗口） / archived（不可见）
- 淘汰三步（run_maintenance 懒触发 + 24h 节流）：
  ① superseded_at > 7 天 → archived
  ② active 且 created_at > 90 天且 hit_count==0 → archived
  ③ 相似 >0.9 且无替代关系的条目对 → conflicts.jsonl 人工队列
- 归档不删除：archived 行保留在 facts.jsonl（include_archived 可查不可见）

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
from difflib import SequenceMatcher
from typing import List, Optional

MEMORY_FILE = "facts.jsonl"
MEMORY_INDEX = "MEMORY.md"          # 仅 v1 旧形态识别/迁移用
CONFLICTS_FILE = "conflicts.jsonl"  # V1-3 相似冲突人工队列
_FACT_RE = re.compile(r"^fact-(.+)-([0-9a-f]{8})\.md$")
_LOCKS: dict = {}
_LOCKS_GUARD = threading.Lock()

# V1-3 淘汰阈值（可 env 覆盖）
SUPERSEDED_ARCHIVE_DAYS = int(os.getenv("MEMORY_SUPERSEDED_ARCHIVE_DAYS", "7"))
ZERO_HIT_ARCHIVE_DAYS = int(os.getenv("MEMORY_ZERO_HIT_ARCHIVE_DAYS", "90"))
CONFLICT_SIMILARITY = float(os.getenv("MEMORY_CONFLICT_SIMILARITY", "0.9"))
MAINTENANCE_INTERVAL_S = 24 * 3600

# 进程内节流（维护 24h 一次 / 命中统计 60s 一次写回）
_maintained_at: dict = {}
_last_hit_write: dict = {}


def _now() -> str:
    # 微秒精度：同批写入时排序稳定（created_at 是「丢最旧」的顺序键）
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")


def _mem_dir(user_id) -> str:
    # 惰性导入：测试 monkeypatch utils.data_path.root_path 才能生效
    # （模块级 from-import 绑定早于 patch，指向原函数）
    from utils.data_path import root_path
    return os.path.join(root_path(), "data", ".yuan", str(user_id))


def _lock_for(user_id) -> threading.RLock:
    # RLock：读路径内会触发维护/写回（load_entries → _maybe_maintain →
    # run_maintenance 再取同一把锁），非重入 Lock 会死锁
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(str(user_id), threading.RLock())


# ==================== v3 条目归一化 ====================

def _new_id() -> str:
    return "f_" + uuid.uuid4().hex[:12]


def _normalize_entry(e: dict) -> dict:
    """条目归一化：v2 存量行补发 id/状态等 v3 字段（懒迁移在读取时完成）"""
    return {
        "id": str(e.get("id") or "") or _new_id(),
        "text": str(e.get("text", "")).strip(),
        "created_at": e.get("created_at", ""),
        "type": e.get("type", "chat"),
        "source": e.get("source", ""),
        "session_id": str(e.get("session_id", "") or ""),
        "turn": int(e.get("turn") or 0),
        "supersedes": str(e.get("supersedes", "") or ""),
        "superseded_by": str(e.get("superseded_by", "") or ""),
        "superseded_at": e.get("superseded_at", ""),
        "last_hit": e.get("last_hit", ""),
        "hit_count": int(e.get("hit_count") or 0),
        "status": e.get("status") or "active",
        "file": e.get("file", ""),  # v1 迁移兼容字段（不落盘）
    }


# ==================== v3 JSONL 读写 ====================

def _read_jsonl(path: str) -> List[dict]:
    """读 facts.jsonl → v3 条目列表（坏行跳过，不因单行损坏丢掉全部记忆）"""
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
                    entries.append(_normalize_entry(obj))
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
                e = _normalize_entry(e)
                if not e["created_at"]:
                    e["created_at"] = (base + timedelta(microseconds=i)).strftime("%Y-%m-%dT%H:%M:%S.%f")
                e.pop("file", None)  # 兼容字段不落盘
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
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


def load_entries(user_id, include_archived: bool = False) -> List[dict]:
    """读记忆条目（created_at 升序 = 最旧在前）；目录不存在返回 []。
    默认只返回 active（归档/被替代条目不可见——只归档不删除）；
    include_archived=True 返回全部（维护/审计用）。
    v1 旧 .md 目录首次读取时懒迁移到 facts.jsonl。读取时懒触发维护（24h 节流）。"""
    d = _mem_dir(user_id)
    if not os.path.isdir(d):
        return []
    jf = os.path.join(d, MEMORY_FILE)
    if os.path.isfile(jf):
        entries = _read_jsonl(jf)
        # v2 → v3 懒迁移：存量行缺 id → 补发后落盘固化（否则每次读取 id 随机变）
        try:
            with open(jf, encoding="utf-8") as f:
                raw = f.read()
            if entries and '"id"' not in raw:
                _write_jsonl(user_id, entries)
        except OSError:
            pass
        entries.sort(key=lambda e: e["created_at"] or "")
        _maybe_maintain(user_id)
        if not include_archived:
            entries = [e for e in entries if e.get("status") == "active"]
        return entries
    # v1 旧形态：读旧条目并迁移（调用方多已持有 per-user 锁；裸调用并发迁移幂等）
    entries = _read_legacy_dir(d)
    entries.sort(key=lambda e: e["created_at"] or "")
    if entries:
        _migrate_legacy(user_id, d, entries)
    return entries


def load_facts(user_id, mark_hit: bool = False) -> List[str]:
    """事实行列表（注入/展示用），最旧在前。mark_hit=True（对话注入点）时
    更新命中统计（hit_count+1/last_hit），供零命中 90 天归档判定。"""
    with _lock_for(user_id):
        entries = load_entries(user_id)
        if mark_hit:
            _mark_hit_locked(user_id, entries)
        return [e["text"] for e in entries]


def rewrite(user_id, lines: List[str], source: str = "edit") -> dict:
    """全量覆盖（设置页 PUT）：与旧条目等键/包含的行复用 id/created_at/命中统计，
    其余记当前时间；清单外的旧条目归档（只归档不删除）。

    返回 {"memory": str, "total": int}
    """
    from yuanai_core.memory import dedup_key
    with _lock_for(user_id):
        old = load_entries(user_id)
        old_keys = [(dedup_key(e["text"]), e) for e in old]
        entries = []
        kept_ids = set()
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
            if reused:
                e = dict(reused)
                e["text"] = ln
                e["source"] = e["source"] or source
                kept_ids.add(e["id"])
                entries.append(e)
            else:
                entries.append({"text": ln, "created_at": "", "type": "chat",
                                "source": source})
        # 清单外旧条目 → 归档（含旧归档行，全量保留）
        with _lock_for(user_id):
            archived = [e for e in load_entries(user_id, include_archived=True)
                        if e["id"] not in kept_ids and e["status"] == "active"]
            for e in archived:
                e["status"] = "archived"
            _write_jsonl(user_id, entries + archived)
        return {"memory": "\n".join(e["text"] for e in entries), "total": len(entries)}


def apply_entries(user_id, entries: List[dict]) -> int:
    """按给定条目全量重写（自整理用；条目形状同 load_entries 输出，
    created_at 空则记当前时间）。清单外的旧条目归档（只归档不删除）。
    返回条目总数。"""
    with _lock_for(user_id):
        clean = [e for e in entries if str(e.get("text", "")).strip()]
        kept_ids = {e.get("id") for e in clean if e.get("id")}
        # 旧行（含已归档）中不在 kept 的 active 行 → 归档
        archived = [e for e in load_entries(user_id, include_archived=True)
                    if e.get("id") not in kept_ids and e.get("status") == "active"]
        for e in archived:
            e["status"] = "archived"
        _write_jsonl(user_id, clean + archived)
        return len(clean)


def add_facts(user_id, new_lines: List[str], max_items: int = 100,
              max_chars: int = 2000, source: str = "fold",
              session_id: str = "", turn: int = 0) -> dict:
    """合并新事实（只追加 + 双向去重 + 超限丢最旧，逻辑复用 yuanai_core.memory.merge_facts）。
    V1-3：新行 ⊃ 旧行 → 显式替代链（新行 supersedes 旧行 id，旧行 superseded）。

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
        now = _now()
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
            if reused:
                e = dict(reused)
                if e["text"] != ln:
                    # 升级语义：新行替代旧行 → 替代链（新行取新 id，旧行 superseded）
                    new_entry = {"id": _new_id(), "text": ln,
                                 "created_at": e["created_at"],
                                 "type": e["type"], "source": source,
                                 "session_id": session_id, "turn": turn,
                                 "supersedes": e["id"]}
                    e["status"] = "superseded"
                    e["superseded_by"] = new_entry["id"]
                    e["superseded_at"] = now
                    entries.append(e)
                    entries.append(new_entry)
                else:
                    e.setdefault("id", _new_id())
                    entries.append(e)
            else:
                entries.append({"text": ln, "created_at": "", "type": "chat",
                                "source": source, "session_id": session_id,
                                "turn": turn})
        _write_jsonl(user_id, entries)
        return {"added": added,
                "total": sum(1 for e in entries if e.get("status", "active") == "active")}


def delete_fact(user_id, keyword: str) -> dict:
    """按文本删除（V1-3：归档，不物理删除——只归档不删除）：先精确匹配
    （strip 相等），无命中再唯一子串匹配。

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
        target = hits[0]
        target["status"] = "archived"
        _write_jsonl(user_id, [e for e in load_entries(user_id, include_archived=True)
                               if e["id"] != target["id"]] + [target])
        remaining = [e["text"] for e in load_entries(user_id)]
        return {"deleted": 1, "total": len(remaining),
                "memory": "\n".join(remaining), "asked_more": False}


# ==================== V1-3 命中统计 / 维护 / 冲突队列 ====================

def _mark_hit_locked(user_id, entries: List[dict]) -> None:
    """命中统计写回（60s 进程内节流——注入每轮一次，避免同轮多次写盘）"""
    import time as _time
    key = str(user_id)
    if _time.time() - _last_hit_write.get(key, 0) < 60:
        return
    if not entries:
        return
    now = _now()
    changed = False
    for e in entries:
        if e.get("status") != "active":
            continue
        e["hit_count"] = int(e.get("hit_count") or 0) + 1
        e["last_hit"] = now
        changed = True
    if changed:
        _last_hit_write[key] = _time.time()
        _write_jsonl(user_id, entries)


def _maybe_maintain(user_id) -> None:
    """读路径懒触发维护（24h 节流）：淘汰/归档/冲突登记全部在此收敛"""
    import time as _time
    key = str(user_id)
    if _time.time() - _maintained_at.get(key, 0) < MAINTENANCE_INTERVAL_S:
        return
    # 先置位再执行：run_maintenance 内部读路径会再进本函数，防递归
    _maintained_at[key] = _time.time()
    try:
        run_maintenance(user_id)
    except Exception:
        pass  # 维护失败绝不影响读路径


def run_maintenance(user_id) -> dict:
    """淘汰三步（V1-3）：① superseded >7 天 → archived ② active 零命中 >90 天
    → archived ③ 相似 >0.9 且无替代关系的条目对 → conflicts.jsonl 人工队列。
    只归档不删除。返回 {"archived": n, "conflicts": m}"""
    import time as _time
    with _lock_for(user_id):
        all_entries = load_entries(user_id, include_archived=True)
        active = [e for e in all_entries if e["status"] == "active"]
        superseded = [e for e in all_entries if e["status"] == "superseded"]
        now = datetime.now()
        changed = False

        def _parse(ts: str) -> Optional[datetime]:
            try:
                return datetime.strptime(str(ts)[:19], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                try:
                    return datetime.fromisoformat(str(ts))
                except ValueError:
                    return None

        archived_n = 0
        for e in superseded:
            t = _parse(e.get("superseded_at") or "")
            if t and (now - t).days >= SUPERSEDED_ARCHIVE_DAYS:
                e["status"] = "archived"
                archived_n += 1
                changed = True
        for e in active:
            if int(e.get("hit_count") or 0) == 0:
                t = _parse(e.get("created_at") or "")
                if t and (now - t).days >= ZERO_HIT_ARCHIVE_DAYS:
                    e["status"] = "archived"
                    archived_n += 1
                    changed = True

        # 相似冲突：active 两两比对 >0.9 且无替代关系 → 人工队列（幂等重写）
        conflicts = []
        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                a, b = active[i], active[j]
                if a.get("supersedes") or a.get("superseded_by") or \
                        b.get("supersedes") or b.get("superseded_by"):
                    continue
                ratio = SequenceMatcher(None, a["text"], b["text"]).ratio()
                if ratio >= CONFLICT_SIMILARITY:
                    conflicts.append({
                        "a_id": a["id"], "b_id": b["id"],
                        "a_text": a["text"][:120], "b_text": b["text"][:120],
                        "similarity": round(ratio, 3),
                        "detected_at": _now(),
                    })
        if conflicts:
            _write_conflicts(user_id, conflicts)

        if changed:
            _write_jsonl(user_id, all_entries)
        _maintained_at[str(user_id)] = _time.time()
        return {"archived": archived_n, "conflicts": len(conflicts)}


def _write_conflicts(user_id, conflicts: List[dict]) -> None:
    d = _mem_dir(user_id)
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f".conflicts-{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            for c in conflicts:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        os.replace(tmp, os.path.join(d, CONFLICTS_FILE))
    finally:
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def list_conflicts(user_id) -> List[dict]:
    """相似冲突人工队列（后台/设置页可列——V1-3 验收点）"""
    path = os.path.join(_mem_dir(user_id), CONFLICTS_FILE)
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        out.append(obj)
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def clear(user_id) -> None:
    """清空该用户全部记忆"""
    with _lock_for(user_id):
        d = _mem_dir(user_id)
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
