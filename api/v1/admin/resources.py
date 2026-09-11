"""后台管理 — 数据/系统资源：网站、文件浏览、模型配置、API Key"""

import os
import base64
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request
from db.session import get_db
from api.v1.middleware import require_admin
from utils.data_path import root_path
from api.v1.models_file import read_models_file as _read_models_file, write_models_file as _write_models_file

router = APIRouter(tags=["admin"])  # 无 prefix：由主 router 统一加 /admin


class WebsiteCreate(BaseModel):
    name: str
    url: str
    remark: str = ""
    sort_order: int = 0


class WebsiteUpdate(BaseModel):
    name: str = None
    url: str = None
    remark: str = None
    sort_order: int = None


# ===================== 网站管理 =====================

@router.get("/websites")
async def list_websites(request: Request):
    require_admin(request)
    db = get_db()
    websites = db.get_websites()
    if not websites:
        # 数据库为空时，从 spiderlx 注册表自动导入
        try:
            from spiderlx.core.save.urls import get_urls
            get_urls()
            websites = db.get_websites()
        except ImportError:
            pass
    return websites


@router.post("/websites")
async def add_website(req: WebsiteCreate, request: Request):
    require_admin(request)
    db = get_db()
    result = db.add_website(req.name, req.url, req.remark, req.sort_order)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.put("/websites/{wid}")
async def edit_website(wid: int, req: WebsiteUpdate, request: Request):
    require_admin(request)
    db = get_db()
    ok = db.update_website(wid, req.name, req.url, req.remark, req.sort_order)
    if not ok:
        raise HTTPException(status_code=404, detail="网站不存在")
    return {"ok": True}


@router.delete("/websites/{wid}")
async def delete_website(wid: int, request: Request):
    require_admin(request)
    db = get_db()
    ok = db.delete_website(wid)
    if not ok:
        raise HTTPException(status_code=404, detail="网站不存在")
    return {"ok": True}


# ===================== 文件管理 =====================

@router.get("/files")
async def list_files(request: Request, path: str = ""):
    require_admin(request)
    base = os.path.realpath(os.path.join(root_path(), "data"))
    target = os.path.realpath(os.path.join(base, path))
    if not target.startswith(base + os.sep) and target != base:
        raise HTTPException(status_code=400, detail="路径越权")
    if not os.path.exists(target):
        return {"path": path, "items": []}
    items = []
    for name in sorted(os.listdir(target)):
        full = os.path.join(target, name)
        rel = os.path.join(path, name) if path else name
        is_dir = os.path.isdir(full)
        size = 0 if is_dir else os.path.getsize(full)
        items.append({"name": name, "path": rel, "is_dir": is_dir, "size_kb": round(size / 1024, 1)})
    return {"path": path, "items": items}


@router.get("/file/read")
async def read_file(request: Request, path: str = ""):
    """读取文件内容（图片返回 base64，文本返回内容）"""
    require_admin(request)
    base = os.path.realpath(os.path.join(root_path(), "data"))
    target = os.path.realpath(os.path.join(base, path))
    if not target.startswith(base + os.sep) and target != base:
        raise HTTPException(status_code=400, detail="路径越权")
    if not os.path.isfile(target):
        raise HTTPException(status_code=404, detail="文件不存在")
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
        with open(target, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        return {"type": "image", "ext": ext, "data": b64}
    if ext in ('.txt', '.csv', '.json', '.py', '.js', '.tsx', '.ts', '.css', '.html', '.md', '.yml', '.yaml', '.xml', '.log'):
        try:
            with open(target, 'r', encoding='utf-8') as f:
                text = f.read()
            return {"type": "text", "content": text}
        except UnicodeDecodeError:
            return {"type": "binary", "detail": "无法解码为文本"}
    return {"type": "unsupported", "detail": f"暂不支持预览 {ext} 文件"}


# ===================== 模型配置 =====================

class ModelUpsert(BaseModel):
    model_id: str
    label: str
    provider: str = "Custom"


class ModelDelete(BaseModel):
    model_id: str


@router.get("/models")
async def list_models(request: Request):
    from config.settings import MODELS, _DEFAULT_MODELS
    result = {}
    for k, v in MODELS.items():
        result[k] = {**v, "builtin": k in _DEFAULT_MODELS}
    return result


@router.post("/models")
async def add_model(req: ModelUpsert, request: Request):
    require_admin(request)
    data = _read_models_file()
    data[req.model_id] = {"label": req.label, "provider": req.provider}
    _write_models_file(data)
    from config.settings import _load_models, MODELS
    MODELS.clear(); MODELS.update(_load_models())
    return {"ok": True, "model_id": req.model_id}


@router.delete("/models")
async def delete_model(req: ModelDelete, request: Request):
    require_admin(request)
    data = _read_models_file()
    if req.model_id in data:
        del data[req.model_id]
        _write_models_file(data)
    from config.settings import _load_models, MODELS
    MODELS.clear(); MODELS.update(_load_models())
    return {"ok": True}


# ===================== API Key =====================

class ApiKeyUpsert(BaseModel):
    provider: str
    key: str


@router.get("/apikeys")
async def list_apikeys(request: Request):
    require_admin(request)
    return _read_models_file().get("_apikeys", {})


@router.post("/apikeys")
async def save_apikey(req: ApiKeyUpsert, request: Request):
    require_admin(request)
    data = _read_models_file()
    keys = data.get("_apikeys", {})
    keys[req.provider] = req.key
    data["_apikeys"] = keys
    _write_models_file(data)
    return {"ok": True}


@router.delete("/apikeys")
async def delete_apikey(req: ApiKeyUpsert, request: Request):
    require_admin(request)
    data = _read_models_file()
    keys = data.get("_apikeys", {})
    keys.pop(req.provider, None)
    if keys:
        data["_apikeys"] = keys
    else:
        data.pop("_apikeys", None)
    _write_models_file(data)
    return {"ok": True}
