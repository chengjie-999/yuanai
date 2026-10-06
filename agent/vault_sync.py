"""Obsidian vault ↔ 云端知识星球 双向同步循环（S2 Agent 侧，纯轮询不引 watchdog）

- 扫描：os.walk vault 同步目录，快照 (size, mtime)
- 防抖：同一路径 (size,mtime) 连续两轮不变 且 now-mtime>3s 才算稳定
- 三向判定：sync_decision(base_hash, vault_hash, cloud_hash)（纯函数已就绪）
- 冷启动：状态文件无基线 → 云端全量下载建基线（本地无锚点文件进 pending_import）
- 增量：1 请求/轮（pull index → 按需 pull content → push ≤20 op）
- 冲突：本地赢，云端版落 *.conflict-<时间>.md（sync_ignore 永不同步）
- 删除：本地删 → trash 归档 + push delete；云端删 → 保守不传播（cloud_deleted 墓碑）
- 错误：笔记级指数退避（5 次后仅 mtime 变化复活）；请求级 20→40→80→300s 封顶
- 状态：data/vault_sync_state.json（原子写 + .bak）

REST 鉴权：X-Agent-Id + X-Agent-Secret 头（对应 api/v1/agent/planet_sync.py）
"""

import json
import logging
import os
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path

from utils.data_path import root_path
from yuanai_core.pure.vault_note import (
    canonical_body, inject_frontmatter, note_body_hash, parse_frontmatter,
    strip_frontmatter, sync_decision, vault_filename,
)

logger = logging.getLogger(__name__)

POLL_SECONDS = 20
DEBOUNCE_ROUNDS = 2
DEBOUNCE_MTIME_AGE_S = 3
PUSH_MAX_OPS = 20
PUSH_MAX_BYTES = 4 * 1024 * 1024
RETRY_MAX = 5
BACKOFF_REQUEST = [20, 40, 80, 300]

SYNC_IGNORE_SUFFIX = ".conflict-"
SYNC_DIR_NAME = "知识星球"


def _atomic_write_json(path: str, data) -> None:
    """原子写 JSON（tmp + os.replace；失败时保留 .bak）"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if os.path.exists(path):
        try:
            shutil.copy2(path, path + ".bak")
        except OSError:
            pass
    os.replace(tmp, path)


class VaultSyncLoop:
    """vault 同步循环（托盘 daemon 线程驱动；run_once 可单步调用便于测试）"""

    def __init__(self, vault_dir: str, agent_id: str, agent_secret: str,
                 server_base: str, status_cb=None, state_path: str = None):
        self.vault_dir = str(vault_dir).rstrip("/\\")
        self.agent_id = str(agent_id)
        self.agent_secret = agent_secret
        self.server_base = server_base.rstrip("/")
        self.status_cb = status_cb  # callback(dict) 状态上报（S4 托盘/前端徽标）
        self.state_path = state_path or os.path.join(root_path(), "data", "vault_sync_state.json")
        self._running = False
        self._snap_prev = {}
        self._snap_prev2 = {}
        self._request_backoff_s = 0
        self._state = self._load_state()
        self._sync_ignore = set(self._state.get("sync_ignore") or [])

    # ---------------- 状态文件 ----------------

    def _load_state(self) -> dict:
        try:
            if os.path.exists(self.state_path):
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("vault 状态文件损坏，冷启动基线: %s", e)
        return {"baseline": False, "planets": {}, "notes": {}, "trash": [],
                "cloud_deleted": [], "sync_ignore": []}

    def _save_state(self) -> None:
        self._state["sync_ignore"] = sorted(self._sync_ignore)
        _atomic_write_json(self.state_path, self._state)

    def _report(self, **kw) -> None:
        if self.status_cb:
            try:
                self.status_cb(kw)
            except Exception:
                pass

    # ---------------- HTTP ----------------

    def _http(self, method: str, path: str, payload: dict = None, timeout: int = 30):
        """urllib 请求（照 agent/main.py do_install 模式）+ Agent 鉴权头"""
        url = f"{self.server_base}/api/v1/agent/planet{path}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("X-Agent-Id", self.agent_id)
        req.add_header("X-Agent-Secret", self.agent_secret)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}

    def _http_ok(self, method: str, path: str, payload: dict = None, timeout: int = 30):
        try:
            return True, self._http(method, path, payload, timeout)
        except urllib.error.HTTPError as e:
            logger.warning("vault 请求 %s %s → HTTP %s", method, path, e.code)
            return False, {"code": e.code}
        except Exception as e:
            logger.warning("vault 请求失败 %s %s: %s", method, path, e)
            return False, {"error": str(e)}

    # ---------------- 扫描 / 防抖 ----------------

    def _scan(self) -> dict:
        """vault 同步目录快照：{rel_path: [size, mtime]}（仅 .md，忽略冲突副本）"""
        snap = {}
        if not os.path.isdir(self.vault_dir):
            return snap
        for dirpath, _dirs, files in os.walk(self.vault_dir):
            for fn in files:
                if not fn.endswith(".md") or SYNC_IGNORE_SUFFIX in fn:
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, self.vault_dir).replace("\\", "/")
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                snap[rel] = [st.st_size, int(st.st_mtime)]
        return snap

    def _debounced_candidates(self, snap: dict, now: float) -> set:
        """连续两轮 (size,mtime) 不变 且 修改时间 >3s 前的路径 = 稳定候选"""
        if not self._snap_prev or not self._snap_prev2:
            return set()
        out = set()
        for rel, cur in snap.items():
            if (self._snap_prev.get(rel) == cur and self._snap_prev2.get(rel) == cur
                    and now - cur[1] > DEBOUNCE_MTIME_AGE_S):
                out.add(rel)
        return out

    # ---------------- 文件级操作 ----------------

    def _read_note(self, rel: str) -> tuple:
        """读 vault 文件 → (text, frontmatter, body, vault_hash)"""
        with open(os.path.join(self.vault_dir, rel), "r", encoding="utf-8") as f:
            text = f.read()
        fm = parse_frontmatter(text)
        body = strip_frontmatter(text)
        mid = int(fm.get("map_id") or 0)
        return text, fm, body, note_body_hash(body, mid)

    def _write_note(self, rel: str, body: str, fields: dict) -> None:
        full = os.path.join(self.vault_dir, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(inject_frontmatter(body, fields))

    def _trash(self, rel: str) -> None:
        """本地删除归档（保留一个副本，不直接 rm）"""
        full = os.path.join(self.vault_dir, rel)
        trash_dir = os.path.join(self.vault_dir, "..", ".yuanai-trash")
        os.makedirs(trash_dir, exist_ok=True)
        try:
            shutil.move(full, os.path.join(trash_dir, os.path.basename(rel) + f".{int(time.time())}"))
        except OSError as e:
            logger.warning("trash 归档失败 %s: %s", rel, e)
        self._state.setdefault("trash", []).append(
            {"path": rel, "time": int(time.time()), "note_id": self._state["notes"].get(rel, {}).get("note_id")})

    # ---------------- 冷启动基线 ----------------

    def _build_baseline(self) -> None:
        """冷启动：云端全量下载 → 落盘（frontmatter 锚点）；本地无锚点文件进 pending_import"""
        ok, data = self._http_ok("GET", "/pull/index")
        if not ok:
            return
        cloud_index = {n["id"]: n for n in data.get("notes", [])}
        if not cloud_index:
            self._state["baseline"] = True
            self._save_state()
            return
        ok, data2 = self._http_ok("GET", f"/pull/content?ids={','.join(map(str, cloud_index.keys()))}")
        if not ok:
            return
        pending = []
        for note in data2.get("notes", []):
            nid = note["id"]
            index = cloud_index.get(nid, {})
            rel = f"{SYNC_DIR_NAME}/{vault_filename(index.get('title') or '笔记')}"
            full = os.path.join(self.vault_dir, rel)
            if os.path.exists(full):
                pending.append(rel)
                continue
            self._write_note(rel, note.get("content") or "",
                             {"planet_note_id": nid, "map_id": note.get("map_id") or 0,
                              "source": "cloud"})
            _, fm, body, h = self._read_note(rel)
            self._state["notes"][rel] = {"note_id": nid, "base_hash": h, "status": "ok", "retry": 0}
        self._state["baseline"] = True
        self._state["pending_import"] = pending
        self._save_state()
        self._report(event="baseline", downloaded=len(cloud_index), pending=len(pending))

    # ---------------- 单步同步 ----------------

    def run_once(self, now: float = None) -> dict:
        """执行一轮同步（幂等；返回本轮摘要，测试直接调用）"""
        now = now or time.time()
        summary = {"cold_start": False, "uploaded": 0, "downloaded": 0,
                   "conflicts": 0, "deleted": 0, "skipped": 0}

        # 请求级退避：上次请求失败后暂停 BACKOFF_REQUEST 阶梯
        if self._request_backoff_s and now < self._request_backoff_s:
            return summary
        self._request_backoff_s = 0

        if not self._state.get("baseline"):
            self._build_baseline()
            summary["cold_start"] = True
        # 基线之后再扫描：基线刚落盘的文件绝不能进删除检测
        snap = self._scan()

        # 1) 拉云端索引
        ok, data = self._http_ok("GET", "/pull/index")
        if not ok:
            self._request_backoff_s = now + BACKOFF_REQUEST[min(
                self._state.get("backoff_level", 0), len(BACKOFF_REQUEST) - 1)]
            self._state["backoff_level"] = min(self._state.get("backoff_level", 0) + 1, 3)
            self._save_state()
            return summary
        self._state["backoff_level"] = 0
        cloud_index = {n["id"]: n for n in data.get("notes", [])}

        candidates = self._debounced_candidates(snap, now)

        # 2) 本地变更 → 三向 → push
        ops = []
        for rel in list(candidates):
            entry = self._state["notes"].get(rel)
            if not entry:  # 无锚点新文件 → 新建上传（首次同步即建行）
                _, fm, body, h = self._read_note(rel)
                ops.append(("new", rel, fm, body, h, entry))
                continue
            try:
                _, fm, body, h = self._read_note(rel)
            except OSError:
                continue
            cloud = cloud_index.get(entry["note_id"])
            cloud_hash = cloud["content_hash"] if cloud else ""
            decision = sync_decision(entry.get("base_hash", ""), h, cloud_hash)
            if decision == "upload":
                ops.append(("upsert", rel, fm, body, h, entry))
            elif decision == "download":
                ops.append(("download", rel, fm, body, h, entry))
            elif decision == "conflict":
                ops.append(("conflict", rel, fm, body, h, entry))

        total_bytes = 0
        for op in ops[:PUSH_MAX_OPS]:
            kind, rel, fm, body, h, entry = op
            total_bytes += len(body)
            if total_bytes > PUSH_MAX_BYTES:
                break
            if kind in ("new", "upsert"):
                ok, r = self._http_ok("POST", "/push/upsert", {
                    "planet": fm.get("planet") or SYNC_DIR_NAME,
                    "map_id": int(fm.get("map_id") or 0),
                    "title": os.path.splitext(os.path.basename(rel))[0],
                    "content": body,
                })
                if not ok:
                    self._mark_failed(rel)
                    continue
                self._state["notes"][rel] = {"note_id": r["id"], "base_hash": r["content_hash"],
                                             "status": "ok", "retry": 0}
                summary["uploaded"] += 1
            elif kind == "download":
                ok, r = self._http_ok("GET", f"/pull/content?ids={entry['note_id']}")
                if not ok:
                    continue
                notes = r.get("notes") or []
                if not notes:
                    continue
                self._write_note(rel, notes[0]["content"], {"planet_note_id": entry["note_id"],
                                                            "map_id": notes[0].get("map_id") or 0,
                                                            "source": "cloud"})
                _, _fm, _b, h2 = self._read_note(rel)
                self._state["notes"][rel]["base_hash"] = h2
                self._state["notes"][rel]["status"] = "ok"
                summary["downloaded"] += 1
            elif kind == "conflict":
                cloud = cloud_index.get(entry["note_id"])
                if cloud:
                    ok, r = self._http_ok("GET", f"/pull/content?ids={entry['note_id']}")
                    if ok and r.get("notes"):
                        conflict_rel = f"{rel[:-3]}{SYNC_IGNORE_SUFFIX}{time.strftime('%Y%m%d-%H%M%S')}.md"
                        self._write_note(conflict_rel, r["notes"][0]["content"],
                                         {"planet_note_id": entry["note_id"], "source": "cloud"})
                        self._sync_ignore.add(conflict_rel)
                # 本地赢：上传本地版
                ok, r2 = self._http_ok("POST", "/push/upsert", {
                    "planet": fm.get("planet") or SYNC_DIR_NAME,
                    "map_id": int(fm.get("map_id") or 0),
                    "title": os.path.splitext(os.path.basename(rel))[0],
                    "content": body,
                })
                if ok:
                    self._state["notes"][rel]["base_hash"] = r2.get("content_hash", h)
                    self._state["notes"][rel]["status"] = "ok"
                summary["conflicts"] += 1

        # 3) 本地删除检测：状态里有、磁盘上没了 → trash + push delete
        for rel in list(self._state["notes"].keys()):
            if rel in snap or rel in self._sync_ignore:
                continue
            entry = self._state["notes"].get(rel) or {}
            self._trash(rel)
            if entry.get("note_id"):
                ok, _ = self._http_ok("POST", "/push/delete", {"nid": entry["note_id"]})
                if ok:
                    summary["deleted"] += 1
            del self._state["notes"][rel]

        # 4) 云端删除：保守不传播（cloud_deleted 墓碑，文件保留不再上传）
        local_nids = {v["note_id"] for v in self._state["notes"].values()}
        self._state["cloud_deleted"] = [
            n["id"] for n in cloud_index.values() if n["id"] not in local_nids]

        self._save_state()
        if summary["uploaded"] or summary["downloaded"] or summary["conflicts"] or summary["deleted"]:
            self._report(event="sync", **summary)
        return summary

    def _mark_failed(self, rel: str) -> None:
        entry = self._state["notes"].setdefault(rel, {"note_id": 0, "base_hash": "", "status": "ok", "retry": 0})
        entry["retry"] = entry.get("retry", 0) + 1
        entry["status"] = "error" if entry["retry"] >= RETRY_MAX else "retrying"

    # ---------------- 循环 ----------------

    def run_loop(self, stop_flag=None, poll: int = POLL_SECONDS):
        """守护线程循环：20s 轮询（sleep 切 1s 片便于退出）"""
        self._running = True
        while self._running:
            try:
                self.run_once()
            except Exception:
                logger.exception("vault 同步轮异常")
            for _ in range(poll):
                if stop_flag is not None and stop_flag():
                    break
                if not self._running:
                    break
                time.sleep(1)
        self._running = False

    def stop(self):
        self._running = False


def load_vault_config(config_path: str) -> dict:
    """读 agent_config.json 的 vault 节（托盘/CLI 共用）"""
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("vault", {}) if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def save_vault_config(config_path: str, vault_cfg: dict) -> None:
    """写 agent_config.json 的 vault 节（读-改-写合并，不覆盖其它节）"""
    data = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    data["vault"] = vault_cfg
    _atomic_write_json(config_path, data)


def build_loop_from_config(config_path: str, agent_id: str, agent_secret: str,
                           server_url: str, status_cb=None):
    """配置 → VaultSyncLoop；未启用/未设路径返回 None"""
    cfg = load_vault_config(config_path)
    vault_dir = (cfg.get("path") or "").strip()
    if not cfg.get("enabled") or not vault_dir or not os.path.isdir(vault_dir):
        return None
    server_base = server_url.replace("ws://", "http://").replace("wss://", "https://").rstrip("/")
    return VaultSyncLoop(vault_dir, agent_id, agent_secret, server_base, status_cb=status_cb)
