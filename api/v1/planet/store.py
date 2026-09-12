"""知识星球服务层 — 路径布局 / 所有权校验 / 批量导入管线。

文件布局（不复用 data/aiprompt：全量重建会以共享身份索引私人笔记，且旧图片路由无鉴权）：
    data/planet/{uid}/{pid}/{mid}/
      origin.<ext>        原始上传文件（保留原文，支持重解析）
      tree.json           统一 schema 的树（见 yuanai_core.pure.mindmap_parser）
      outline.md          树生成的大纲（导图大纲视图 + LLM 输入共用）
      assets/*            从文档抽出的图片（data: URI 就地解码 / 同名上传文件复制）

所有权原则：所有取数函数首参带 uid 并 filter_by user_id，查不到抛 404（不泄露资源存在性）。
"""
import base64
import json
import os
import re
import shutil
import time

from fastapi import HTTPException

from db.session import get_db
from yuanai_core.pure.mindmap_parser import (
    FIDELITY,
    detect_format,
    parse_any,
    tree_to_outline_md,
)
from utils.data_path import root_path

PLANET_DIR = os.path.join(root_path(), "data", "planet")
MAX_ORIGIN_MB = 50
JOB_TIMEOUT_S = 1200
_DATA_URI_RE = re.compile(r"^data:([a-zA-Z0-9/+.-]+);base64,(.+)$", re.S)
_IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"}


def planet_root() -> str:
    os.makedirs(PLANET_DIR, exist_ok=True)
    return PLANET_DIR


def map_dir(uid: int, pid: int, mid: int) -> str:
    return os.path.join(PLANET_DIR, str(uid), str(pid), str(mid))


def assets_dir(uid: int, pid: int, mid: int) -> str:
    return os.path.join(map_dir(uid, pid, mid), "assets")


def _db():
    return get_db()


# ---------------- 所有权校验（单点实现，越权一律 404） ----------------

def owned_planet(pid: int, uid: int) -> dict:
    p = _db().get_planet(pid, user_id=uid)
    if not p:
        raise HTTPException(status_code=404, detail="星球不存在")
    return p


def owned_map(mid: int, uid: int) -> dict:
    m = _db().get_map(mid, user_id=uid)
    if not m:
        raise HTTPException(status_code=404, detail="导图不存在")
    return m


def owned_note(nid: int, uid: int) -> dict:
    n = _db().get_note(nid, user_id=uid)
    if not n:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return n


def owned_job(jid: int, uid: int) -> dict:
    j = _db().get_job(jid, user_id=uid)
    if not j:
        raise HTTPException(status_code=404, detail="任务不存在")
    return j


def apply_job_watchdog(db, jid: int, uid: int, j: dict) -> str:
    """running 任务超过 JOB_TIMEOUT_S 未更新 → 判 failed（线程无法安全强杀，用轮询看门狗）"""
    if j["status"] != "running":
        return j["status"]
    try:
        t = time.mktime(time.strptime(j["update_time"], "%Y-%m-%d %H:%M:%S"))
        if time.time() - t > JOB_TIMEOUT_S:
            db.update_job(jid, uid, status="failed", error="任务超时，可重试")
            j["status"] = "failed"
            j["error"] = "任务超时，可重试"
            return "failed"
    except ValueError:
        pass
    return "running"


# ---------------- 导入管线（线程池内同步执行） ----------------

def _decode_data_uri(src: str) -> tuple[str, bytes] | None:
    """data:image/png;base64,... → (扩展名, 二进制)；非 data URI 返回 None"""
    m = _DATA_URI_RE.match(src)
    if not m:
        return None
    mime = m.group(1).lower()
    ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg",
               "image/gif": ".gif", "image/svg+xml": ".svg", "image/webp": ".webp",
               "image/bmp": ".bmp"}
    ext = ext_map.get(mime, ".png")
    try:
        return ext, base64.b64decode(m.group(2))
    except Exception:
        return None


def _extract_assets(tree: dict, uid: int, pid: int, mid: int, batch_files: dict[str, bytes]) -> tuple[list, list]:
    """把树里节点的图片落地到 assets/：
    - data: URI → 就地解码写文件
    - 相对文件名 → 在本次上传批次里按 basename 查找并复制
    返回 (写入数, 未解析的 src 列表)。所有未命中的 src 保留原样（前端 404 兜底）。"""
    adir = assets_dir(uid, pid, mid)
    os.makedirs(adir, exist_ok=True)
    written, unresolved = 0, []

    def walk(nodes):
        nonlocal written
        for n in nodes:
            for img in n.get("images", []):
                src = img.get("src", "")
                uri = _decode_data_uri(src)
                if uri:
                    ext, raw = uri
                    fname = f"img{written + 1}{ext}"
                    with open(os.path.join(adir, fname), "wb") as f:
                        f.write(raw)
                    img["src"] = fname
                    written += 1
                else:
                    base = os.path.basename(src).split("?")[0]
                    if base and base in batch_files and base.lower().endswith(tuple(_IMG_EXTS)):
                        with open(os.path.join(adir, base), "wb") as f:
                            f.write(batch_files[base])
                        img["src"] = base
                        written += 1
                    else:
                        unresolved.append(src)
            walk(n.get("children", []))

    walk(tree.get("children", []))
    return written, unresolved


def _group_by_stem(items: list[tuple[str, str, bytes]]) -> list[dict]:
    """同批次去重合并：按（相对目录, 去扩展名 stem）分组，每组取保真度最高者。
    items = [(filename, relpath, raw_bytes)]（webkitRelativePath 与文件平行对齐）。"""
    groups: dict[tuple, dict] = {}
    for filename, rel, raw in items:
        if len(raw) > MAX_ORIGIN_MB * 1024 * 1024:
            continue
        rel = (rel or filename or "").replace("\\", "/")
        dirname, base = os.path.split(rel)
        stem = os.path.splitext(base)[0]
        fmt = detect_format(base, raw)
        g = groups.setdefault((dirname, stem), {"files": []})
        g["files"].append({"filename": base, "fmt": fmt, "raw": raw, "path": rel})
    for g in groups.values():
        # 按保真度排序取最优，其余记入忽略清单
        g["files"].sort(key=lambda x: FIDELITY.index(x["fmt"]) if x["fmt"] in FIDELITY else 99)
        g["chosen"] = g["files"][0]
        g["ignored"] = [f"{x['filename']}({x['fmt']})" for x in g["files"][1:]]
    return list(groups.values())


def _resolve_planet(db, uid: int, name: str) -> int:
    """按名称取星球，不存在则创建（文件夹导入的傻瓜式自动归星）"""
    for p in db.list_planets(uid):
        if p["name"] == name:
            return p["id"]
    return db.create_planet(uid, name)["id"]


def run_import(job_id: int, uid: int, planet_id: int, items: list[tuple[str, str, bytes]],
               auto_planet: str = "") -> None:
    """导入执行体（在 planet 线程池中运行）：分组择优 → 解析 → 落盘 → 建行。"""
    db = _db()
    results = []

    def report(done: int, total: int, msg: str):
        db.update_job(job_id, uid, progress=int(done / max(total, 1) * 100),
                      done_steps=done, total_steps=total, message=msg[:500])

    groups = _group_by_stem(items)
    if not groups:
        db.update_job(job_id, uid, status="failed", error="没有可导入的文件（均为空或超过大小限制）")
        return

    # 批量图库：整个批次的文件按 basename 索引，供 md 相对路径图片复制
    batch_files = {}
    for g in groups:
        for x in g["files"]:
            batch_files[x["filename"]] = x["raw"]

    # 星球路由：paths 首段目录名（自动归星/建星）> 表单 planet_id > 收件箱
    pid = _resolve_planet(db, uid, auto_planet) if auto_planet else planet_id
    if not pid:
        pid = _resolve_planet(db, uid, "收件箱")
    owned_planet(pid, uid)

    total = len(groups)
    for idx, g in enumerate(groups):
        chosen = g["chosen"]
        stem = os.path.splitext(chosen["filename"])[0]
        report(idx, total, f"正在解析 {chosen['filename']}")
        try:
            tree = parse_any(chosen["filename"], chosen["raw"])
        except Exception as e:
            results.append({"filename": chosen["filename"], "ok": False, "error": str(e)})
            report(idx + 1, total, f"解析失败 {chosen['filename']}")
            continue

        # 先建行拿 mid，再落盘（目录名用 mid，重名导图互不覆盖）
        warnings = list(tree["meta"].get("warnings", []))
        if g["ignored"]:
            warnings.append(f"同批次同名文件已择优导入，忽略: {'、'.join(g['ignored'])}")
        meta = tree["meta"]
        mid = db.add_map(
            uid, pid, stem, meta.get("format", "txt"), chosen["filename"],
            "", meta.get("node_count", 0), meta.get("max_depth", 0),
            meta.get("quality", "flat"), warnings,
        )

        mdir = map_dir(uid, pid, mid)
        os.makedirs(mdir, exist_ok=True)
        with open(os.path.join(mdir, "origin" + os.path.splitext(chosen["filename"])[1]), "wb") as f:
            f.write(chosen["raw"])
        with open(os.path.join(mdir, "tree.json"), "w", encoding="utf-8") as f:
            json.dump(tree, f, ensure_ascii=False)
        with open(os.path.join(mdir, "outline.md"), "w", encoding="utf-8") as f:
            f.write(tree_to_outline_md(tree))
        img_count, unresolved = _extract_assets(tree, uid, pid, mid, batch_files)
        if unresolved:
            warnings.append(f"{len(unresolved)} 张图片未解析（{unresolved[0] if unresolved else ''}...）")
            db.update_map(mid, uid, warnings=json.dumps(warnings, ensure_ascii=False))

        db.update_map(mid, uid, dir_path=f"{uid}/{pid}/{mid}")
        results.append({"filename": chosen["filename"], "ok": True, "map_id": mid,
                        "nodes": meta.get("node_count", 0), "images": img_count,
                        "quality": meta.get("quality"), "format": meta.get("format")})
        report(idx + 1, total, f"已导入 {chosen['filename']}")

    ok = [r for r in results if r.get("ok")]
    failed = [r for r in results if not r.get("ok")]
    db.update_job(job_id, uid, status="done" if ok else "failed", progress=100,
                  message=f"导入完成：成功 {len(ok)}，失败 {len(failed)}",
                  result_json=json.dumps({"results": results}, ensure_ascii=False))
    if failed:
        db.update_job(job_id, uid, error="; ".join(r["filename"] for r in failed))


# ---------------- 删除级联 ----------------

def delete_planet_cascade(uid: int, pid: int):
    """删星球：DB 行（内部级联）+ 文件目录。Milvus 索引由 P2 接入后追加。"""
    if not _db().delete_planet(pid, uid):
        raise HTTPException(status_code=404, detail="星球不存在")
    shutil.rmtree(os.path.join(PLANET_DIR, str(uid), str(pid)), ignore_errors=True)


def delete_map_cascade(uid: int, mid: int):
    row = _db().delete_map(mid, uid)
    if not row:
        raise HTTPException(status_code=404, detail="导图不存在")
    shutil.rmtree(map_dir(uid, row["planet_id"], mid), ignore_errors=True)
