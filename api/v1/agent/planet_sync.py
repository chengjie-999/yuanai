"""Obsidian vault 同步 API — 本地 Agent 专用（S1 云端地基）

鉴权链（端点自带，不走用户 JWT 中间件）：
X-Agent-Id + X-Agent-Secret 头 → _verify_agent_secret → resolve_agent_uid
（AgentDevice 一对一绑定映射）→ 未绑定 403「设备未绑定账号」。

端点：
- GET  /pull/index          笔记索引（id/map_id/title/content_hash/update_time）
- GET  /pull/content?ids=   批量正文（≤50 个/次）
- POST /push/upsert         幂等覆盖写入（按 map_id 定位；source='user'）
- POST /push/delete         删除（含 Milvus 索引清理）
- GET  /asset/{mid}/{name}  导图资产下载（vault 图片落盘用；无 ?token=）
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/agent/planet", tags=["agent-planet"])

MAX_BATCH_IDS = 50
MAX_NOTE_CHARS = 200_000  # 单笔记上行上限（MEDIUMTEXT 16MB，防御性收口）


def _agent_uid(request: Request) -> int:
    from api.v1.agent.router import _verify_agent_secret, resolve_agent_uid

    agent_id = request.headers.get("X-Agent-Id", "")
    secret = request.headers.get("X-Agent-Secret", "")
    if not _verify_agent_secret(agent_id, secret):
        raise HTTPException(status_code=401, detail="Agent 凭据无效")
    uid = resolve_agent_uid(agent_id)
    if not uid:
        raise HTTPException(status_code=403, detail="设备未绑定账号")
    return uid


class UpsertBody(BaseModel):
    planet: str = "收件箱"
    map_id: int = 0
    title: str = ""
    content: str


class DeleteBody(BaseModel):
    nid: int


@router.get("/pull/index")
def pull_index(request: Request):
    from db.session import get_db
    uid = _agent_uid(request)
    return {"notes": get_db().list_notes_index(uid)}


@router.get("/pull/content")
def pull_content(request: Request, ids: str = Query(..., description="逗号分隔的笔记 id")):
    uid = _agent_uid(request)
    try:
        nids = [int(x) for x in ids.split(",") if x.strip()][:MAX_BATCH_IDS]
    except ValueError:
        raise HTTPException(status_code=400, detail="ids 格式错误")
    from db.session import get_db
    return {"notes": get_db().get_notes_content(uid, nids)}


@router.post("/push/upsert")
def push_upsert(request: Request, body: UpsertBody):
    """幂等覆盖写入：map_id>0 时按 map_id 定位（存在覆盖/不存在新建）"""
    uid = _agent_uid(request)
    if len(body.content) > MAX_NOTE_CHARS:
        raise HTTPException(status_code=400, detail="笔记内容过大")
    from db.session import get_db
    from api.v1.planet import store
    from yuanai_core.pure.vault_note import note_body_hash

    db = get_db()
    r = store.upsert_note_from_sync(db, uid, body.planet, body.map_id,
                                    body.title, body.content)
    # 同步上行后重建检索索引（vault 编辑的内容聊天里要能搜到；
    # Milvus 异常时内部降级跳过，不影响同步主流程）
    if body.map_id:
        try:
            pid = db.get_note(r["id"], uid)["planet_id"]
            store.index_note(db, uid, pid, body.map_id, body.content)
        except Exception:
            pass
    return {"id": r["id"], "created": r["created"],
            "content_hash": note_body_hash(body.content, body.map_id)}


@router.post("/push/delete")
def push_delete(request: Request, body: DeleteBody):
    uid = _agent_uid(request)
    from db.session import get_db
    from api.v1.planet import store

    if not store.delete_note_from_sync(get_db(), uid, body.nid):
        raise HTTPException(status_code=404, detail="笔记不存在")
    return {"ok": True}


@router.get("/asset/{mid}/{name}")
def get_asset(request: Request, mid: int, name: str):
    """导图资产下载（vault 图片落盘用）。归属校验：设备绑定用户拥有该导图。"""
    from fastapi.responses import FileResponse

    uid = _agent_uid(request)
    from api.v1.planet import store

    m = store.owned_map(mid, uid)
    base = store.assets_dir(uid, m["planet_id"], mid)
    import os
    fp = os.path.normpath(os.path.join(base, name))
    if not fp.startswith(base) or not os.path.isfile(fp):
        raise HTTPException(status_code=404, detail="资源不存在")
    return FileResponse(fp)
