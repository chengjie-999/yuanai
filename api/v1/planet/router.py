"""知识星球 API — 星球/导图/笔记/导入任务

- 所有端点鉴权走全局中间件；所有权校验在 store（越权一律 404）
- 耗时操作（解析/落盘）放 planet 线程池 + jobs 表轮询
- 图片资产走 query token（<img> 无法带 Authorization 头），见 middleware._extract_token
"""
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from api.v1.middleware import get_user_id
from api.v1.planet import store
from db.session import get_db

router = APIRouter(prefix="/api/v1/planet", tags=["planet"])

# 知识星球专用线程池（导入/转换共用，最多 2 个并发）
_planet_executor = ThreadPoolExecutor(max_workers=2)


def _uid(request: Request) -> int:
    uid = get_user_id(request)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    return uid


class PlanetBody(BaseModel):
    name: str
    description: str = ""
    sort_order: int = 0


class PlanetPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None


class NoteBody(BaseModel):
    title: str = ""
    content: str
    planet_id: int = 0
    map_id: Optional[int] = None


def _job_json(j: dict, uid: int) -> dict:
    """轮询响应；超时看门狗把假死 running 判为 failed"""
    store.apply_job_watchdog(get_db(), j["id"], uid, j)
    return {"id": j["id"], "job_type": j["job_type"], "status": j["status"],
            "progress": j["progress"], "total_steps": j["total_steps"],
            "done_steps": j["done_steps"], "message": j["message"], "error": j["error"],
            "result_json": j["result_json"], "planet_id": j["planet_id"], "map_id": j["map_id"]}


# ====================== 星球 CRUD ======================

@router.get("/list")
def list_planets(request: Request):
    uid = _uid(request)
    return {"planets": get_db().list_planets(uid)}


@router.post("/")
def create_planet(request: Request, body: PlanetBody):
    uid = _uid(request)
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="星球名称不能为空")
    p = get_db().create_planet(uid, body.name.strip(), body.description, body.sort_order)
    return {"ok": True, "planet": p}


@router.patch("/{pid}")
def update_planet(request: Request, pid: int, body: PlanetPatch):
    uid = _uid(request)
    store.owned_planet(pid, uid)
    ok = get_db().update_planet(pid, uid, name=body.name, description=body.description,
                                sort_order=body.sort_order)
    return {"ok": ok}


@router.delete("/{pid}")
def delete_planet(request: Request, pid: int):
    uid = _uid(request)
    store.delete_planet_cascade(uid, pid)
    return {"ok": True}


# ====================== 导图 ======================

@router.get("/{pid}/maps")
def list_maps(request: Request, pid: int):
    uid = _uid(request)
    store.owned_planet(pid, uid)
    return {"maps": get_db().list_maps(pid, user_id=uid)}


@router.post("/{pid}/import")
async def import_maps(request: Request, pid: int,
                      files: list[UploadFile] = File(...),
                      paths: list[str] = Form(default=[])):
    """批量导入（多文件 / webkitdirectory 文件夹）。files 与 paths 平行对齐。"""
    uid = _uid(request)
    store.owned_planet(pid, uid)
    if get_db().has_running_job(uid, "import"):
        raise HTTPException(status_code=409, detail="已有导入任务进行中，请稍候")

    # 先把字节读进内存再交给线程池（UploadFile 在请求结束后即被关闭）
    items: list[tuple[str, str, bytes]] = []
    for i, f in enumerate(files):
        raw = await f.read()
        rel = paths[i] if i < len(paths) else (f.filename or "")
        items.append((f.filename or "", rel, raw))
    if not items:
        raise HTTPException(status_code=400, detail="未收到文件")

    # 星球路由：paths 首段目录名自动归星（仅当全部属于同一目录时）
    auto_planet = ""
    if paths and all("/" in p for p in paths):
        first = paths[0].split("/")[0]
        if first and all(p.split("/")[0] == first for p in paths):
            auto_planet = first

    job_id = get_db().create_job(uid, "import", planet_id=pid)
    loop = asyncio.get_running_loop()
    loop.run_in_executor(_planet_executor, store.run_import, job_id, uid, pid, items, auto_planet)
    return {"ok": True, "job_id": job_id}


@router.get("/maps/{mid}")
def get_map(request: Request, mid: int):
    uid = _uid(request)
    return {"map": store.owned_map(mid, uid)}


@router.get("/maps/{mid}/tree")
def get_map_tree(request: Request, mid: int):
    uid = _uid(request)
    m = store.owned_map(mid, uid)
    path = os.path.join(store.map_dir(uid, m["planet_id"], mid), "tree.json")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="树文件不存在")
    return FileResponse(path, media_type="application/json")


@router.get("/maps/{mid}/outline")
def get_map_outline(request: Request, mid: int):
    uid = _uid(request)
    m = store.owned_map(mid, uid)
    path = os.path.join(store.map_dir(uid, m["planet_id"], mid), "outline.md")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="大纲文件不存在")
    return FileResponse(path, media_type="text/markdown; charset=utf-8")


@router.delete("/maps/{mid}")
def delete_map(request: Request, mid: int):
    uid = _uid(request)
    store.delete_map_cascade(uid, mid)
    return {"ok": True}


# ====================== 笔记 ======================

@router.get("/notes")
def list_notes(request: Request, pid: int = 0, mid: int = 0):
    uid = _uid(request)
    return {"notes": get_db().list_notes(uid, planet_id=pid or None, map_id=mid or None)}


@router.get("/notes/{nid}")
def get_note(request: Request, nid: int):
    uid = _uid(request)
    return {"note": store.owned_note(nid, uid)}


@router.put("/notes/{nid}")
def update_note(request: Request, nid: int, body: NoteBody):
    """编辑笔记（用户手改，source 转 user）"""
    uid = _uid(request)
    store.owned_note(nid, uid)
    ok = get_db().update_note(nid, uid, content=body.content, title=body.title or None,
                              summary=None, source="user")
    return {"ok": ok}


@router.post("/notes")
def create_note(request: Request, body: NoteBody):
    """新建自由笔记（可挂在星球下，不关联导图）"""
    uid = _uid(request)
    pid = body.planet_id
    if not pid:
        pid = store._resolve_planet(get_db(), uid, "收件箱")
    store.owned_planet(pid, uid)
    nid = get_db().add_note(uid, pid, body.map_id, body.title or "未命名笔记",
                            body.content, source="user")
    return {"ok": True, "note_id": nid}


@router.delete("/notes/{nid}")
def delete_note(request: Request, nid: int):
    uid = _uid(request)
    row = get_db().delete_note(nid, uid)
    if not row:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return {"ok": True}


# ====================== 任务 ======================

@router.get("/jobs/{jid}")
def get_job(request: Request, jid: int):
    uid = _uid(request)
    j = store.owned_job(jid, uid)
    return _job_json(j, uid)


# ====================== 图片资产（query token 鉴权） ======================

@router.get("/asset/{pid}/{mid}/{filename}")
def serve_asset(request: Request, pid: int, mid: int, filename: str):
    uid = _uid(request)
    m = store.owned_map(mid, uid)
    if m["planet_id"] != pid:
        raise HTTPException(status_code=404, detail="资源不存在")
    base = os.path.realpath(os.path.join(store.assets_dir(uid, pid, mid), ""))
    fp = os.path.normpath(os.path.join(base, filename))
    # realpath 归一化防路径穿越（照 chat/router.py 图片服务安全写法）
    if not fp.startswith(base) or not os.path.isfile(fp):
        raise HTTPException(status_code=404, detail="资源不存在")
    return FileResponse(fp, headers={"Cache-Control": "private, max-age=600"})
