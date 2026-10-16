"""后台管理 — 数据/系统资源：网站、文件浏览、模型配置、API Key"""

import os
import base64
from pydantic import BaseModel
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
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

def _is_hidden_entry(rel_dir: str, name: str) -> bool:
    """文件列表过滤：data 根级隐藏 '.' 开头条目（.yuan 记忆内部存储、
    .pt_token.txt 令牌等敏感 dotfile 不对外暴露）；子层不隐藏"""
    return not rel_dir and name.startswith(".")


@router.get("/files")
async def list_files(request: Request, path: str = ""):
    require_admin(request)
    path = (path or "").replace("\\", "/")
    target = _resolve_in_data(path)
    if not os.path.exists(target):
        return {"path": path, "items": []}
    items = []
    for name in sorted(os.listdir(target)):
        if _is_hidden_entry(path, name):
            continue
        full = os.path.join(target, name)
        # 正斜杠拼接（Windows 下 os.path.join 会产出 \ 脏路径）
        rel = f"{path}/{name}" if path else name
        is_dir = os.path.isdir(full)
        size = 0 if is_dir else os.path.getsize(full)
        items.append({"name": name, "path": rel, "is_dir": is_dir, "size_kb": round(size / 1024, 1)})
    return {"path": path, "items": items}


@router.get("/file/read")
async def read_file(request: Request, path: str = ""):
    """读取文件内容（图片返回 base64，HTML 走渲染预览，其余文本返回内容）"""
    require_admin(request)
    path = (path or "").replace("\\", "/")
    target = _resolve_in_data(path)
    if not os.path.isfile(target):
        raise HTTPException(status_code=404, detail="文件不存在")
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
        with open(target, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        return {"type": "image", "ext": ext, "data": b64}
    if ext == '.html':
        # HTML 渲染预览（iframe 走 /file-html 端点 + 沙箱）；content 供「源码」切换
        try:
            with open(target, 'r', encoding='utf-8') as f:
                text = f.read()
        except UnicodeDecodeError:
            text = ""
        return {"type": "html", "path": path, "content": text}
    if ext == '.md':
        # Markdown 渲染预览（前端 MarkdownContent）；content 供「源码」切换
        try:
            with open(target, 'r', encoding='utf-8') as f:
                text = f.read()
        except UnicodeDecodeError:
            text = ""
        return {"type": "markdown", "path": path, "content": text}
    if ext == '.csv':
        try:
            with open(target, 'r', encoding='utf-8') as f:
                text = f.read(512 * 1024)
        except UnicodeDecodeError:
            text = ""
        return {"type": "csv", "path": path, "content": text}
    if ext == '.json':
        try:
            with open(target, 'r', encoding='utf-8') as f:
                text = f.read(512 * 1024)
        except UnicodeDecodeError:
            text = ""
        return {"type": "json", "path": path, "content": text}
    if ext in ('.mp4', '.webm', '.mov', '.m4v', '.mp3', '.wav', '.m4a', '.ogg'):
        return {"type": "media", "path": path, "ext": ext}
    if ext == '.pdf':
        return {"type": "pdf", "path": path}
    if ext in ('.txt', '.py', '.js', '.tsx', '.ts', '.css', '.yml', '.yaml', '.xml', '.log'):
        try:
            with open(target, 'r', encoding='utf-8') as f:
                text = f.read()
            return {"type": "text", "content": text}
        except UnicodeDecodeError:
            return {"type": "binary", "detail": "无法解码为文本"}
    return {"type": "unsupported", "detail": f"暂不支持预览 {ext} 文件"}


@router.get("/file-media")
async def serve_file_media(request: Request, path: str = ""):
    """音视频/PDF 流式播放（FileResponse 自带 Range 支持，可拖动进度条）"""
    require_admin(request)
    path = (path or "").replace("\\", "/")
    target = _resolve_in_data(path)
    if not os.path.isfile(target):
        raise HTTPException(status_code=404, detail="文件不存在")
    ext = os.path.splitext(path)[1].lower()
    media_types = {
        '.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime',
        '.m4v': 'video/x-m4v', '.mp3': 'audio/mpeg', '.wav': 'audio/wav',
        '.m4a': 'audio/mp4', '.ogg': 'audio/ogg', '.pdf': 'application/pdf',
    }
    media_type = media_types.get(ext)
    if not media_type:
        raise HTTPException(status_code=404, detail="不支持的文件类型")
    from fastapi.responses import FileResponse
    return FileResponse(target, media_type=media_type,
                        headers={"Cache-Control": "private, max-age=600"})


_PROTECTED_DATA_ROOTS = {"chat_images", "qimg", "datasets", "analysis", "planet",
                          "logs", "aiprompt", "file", "crawl", "cases",
                          ".yuan", "user_files"}


def _is_protected_root(target: str) -> bool:
    """data/ 一级关键目录保护（系统数据目录禁止改名/删除）"""
    data_root = os.path.realpath(os.path.join(root_path(), "data"))
    return (os.path.dirname(target) == data_root
            and os.path.basename(target) in _PROTECTED_DATA_ROOTS)


def _resolve_in_data(path: str):
    """realpath 包含校验（文件管理读写共用）；越权抛 400；.yuan 记忆内部存储封禁 404"""
    p = (path or "").replace("\\", "/")
    base = os.path.realpath(os.path.join(root_path(), "data"))
    target = os.path.realpath(os.path.join(base, p))
    if not (target == base or target.startswith(base + os.sep)):
        raise HTTPException(status_code=400, detail="路径越权")
    # 记忆内部存储（data/.yuan/{uid}/）不对外暴露：列表已隐藏，此处防手构造 URL
    rel = os.path.relpath(target, base)
    if rel.split(os.sep)[0] == ".yuan":
        raise HTTPException(status_code=404, detail="文件不存在")
    return target


@router.post("/file/upload")
async def upload_file(request: Request, path: str = "", file: UploadFile = File(...)):
    """上传文件到 data/ 目录（文件名净化 + 100MB 上限）"""
    require_admin(request)
    from utils.safe import safe_filename
    try:
        name = safe_filename(file.filename or "")
    except ValueError:
        raise HTTPException(status_code=400, detail="文件名非法")
    target_dir = _resolve_in_data(path)
    if not os.path.isdir(target_dir):
        raise HTTPException(status_code=400, detail="目标目录不存在")
    dest = os.path.join(target_dir, name)
    if os.path.exists(dest):
        raise HTTPException(status_code=409, detail="同名文件已存在")
    size = 0
    with open(dest, "wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > 100 * 1024 * 1024:
                out.close()
                os.remove(dest)
                raise HTTPException(status_code=400, detail="文件超过 100MB 上限")
            out.write(chunk)
    return {"ok": True, "name": name, "size_kb": round(size / 1024, 1)}


class FileOpBody(BaseModel):
    path: str = ""
    name: str = ""  # 新建目录名 / 重命名目标名


@router.post("/file/mkdir")
async def make_dir(request: Request, body: FileOpBody):
    require_admin(request)
    from utils.safe import safe_filename
    try:
        name = safe_filename(body.name)
    except ValueError:
        raise HTTPException(status_code=400, detail="目录名非法（仅中英文/数字/下划线/点/横线）")
    target = _resolve_in_data(body.path)
    new_dir = os.path.join(target, name)
    if os.path.exists(new_dir):
        raise HTTPException(status_code=409, detail="同名目录已存在")
    os.makedirs(new_dir, exist_ok=True)
    return {"ok": True}


@router.post("/file/rename")
async def rename_file(request: Request, body: FileOpBody):
    """重命名文件/目录（同一目录内；保护 data/ 根下的关键目录不被改名）"""
    require_admin(request)
    from utils.safe import safe_filename
    try:
        name = safe_filename(body.name)
    except ValueError:
        raise HTTPException(status_code=400, detail="新名称非法")
    target = _resolve_in_data(body.path)
    if not os.path.exists(target):
        raise HTTPException(status_code=404, detail="文件不存在")
    if _is_protected_root(target):
        raise HTTPException(status_code=400, detail="不允许重命名系统数据目录")
    new_path = os.path.join(os.path.dirname(target), name)
    if os.path.exists(new_path):
        raise HTTPException(status_code=409, detail="同名项已存在")
    os.rename(target, new_path)
    return {"ok": True, "name": name}


@router.delete("/file/delete")
async def delete_file(request: Request, path: str = ""):
    """删除文件或空目录（保护 data/ 根目录项；非空目录拒绝）"""
    require_admin(request)
    target = _resolve_in_data(path)
    if not os.path.exists(target):
        raise HTTPException(status_code=404, detail="文件不存在")
    if _is_protected_root(target):
        raise HTTPException(status_code=400, detail="不允许删除系统数据目录")
    if os.path.isdir(target):
        if os.listdir(target):
            raise HTTPException(status_code=400, detail="目录非空，请先清空再删除")
        os.rmdir(target)
    else:
        os.remove(target)
    return {"ok": True}


@router.get("/file-html")
async def serve_file_html(request: Request, path: str = ""):
    """HTML 文件渲染预览（iframe 加载；S1.2 同款沙箱头防存储型 XSS）"""
    require_admin(request)
    path = (path or "").replace("\\", "/")
    target = _resolve_in_data(path)
    if not os.path.isfile(target) or not path.lower().endswith(".html"):
        raise HTTPException(status_code=404, detail="文件不存在")
    from fastapi.responses import HTMLResponse
    with open(target, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content, headers={
        "Content-Security-Policy": "sandbox allow-scripts; frame-ancestors 'self'",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-cache",
    })


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
    # 模型淘汰可更换（2026-10-16）：被 Agent 分配引用的模型先切换再删，防分配悬空
    from config.settings import AGENT_MODEL_MAP
    used_by = [k for k, v in AGENT_MODEL_MAP.items() if v == req.model_id]
    if used_by:
        raise HTTPException(status_code=400, detail=(
            f"模型 {req.model_id} 正被使用（{'、'.join(used_by)}），"
            f"请先在「Agent 模型分配」切换到其他模型再删除"))
    data = _read_models_file()
    if req.model_id in data:
        del data[req.model_id]
        _write_models_file(data)
    from config.settings import _load_models, MODELS
    MODELS.clear(); MODELS.update(_load_models())
    return {"ok": True}


# ===================== Agent 模型分配（模型淘汰可更换） =====================

# 分配键白名单（settings._DEFAULT_AGENT_MODEL_MAP 的全部键）
_AGENT_MODEL_KEYS = ("orchestrator", "collection", "analysis", "automation",
                     "audit", "memory_fold", "planet_article")


class AgentModelsUpdate(BaseModel):
    agent_models: dict


@router.get("/agent-models")
async def get_agent_models(request: Request):
    """Agent 模型分配表（当前生效值，含默认）"""
    require_admin(request)
    from config.settings import AGENT_MODEL_MAP
    return {"agent_models": dict(AGENT_MODEL_MAP)}


@router.put("/agent-models")
async def update_agent_models(req: AgentModelsUpdate, request: Request):
    """更新 Agent 模型分配：写 models.json _agent_models + 热更新（无需重启）"""
    require_admin(request)
    from config.settings import MODELS, reload_agent_models
    incoming = req.agent_models or {}
    for k, v in incoming.items():
        if k not in _AGENT_MODEL_KEYS:
            raise HTTPException(status_code=400, detail=f"未知分配项: {k}")
        if not isinstance(v, str) or not v or v not in MODELS:
            raise HTTPException(status_code=400, detail=f"模型不存在或未配置: {v}")
    data = _read_models_file()
    merged = dict(data.get("_agent_models") or {})
    merged.update(incoming)
    data["_agent_models"] = merged
    _write_models_file(data)
    reload_agent_models()
    return {"ok": True}


# ===================== 模型自动检查更新（确认后自动添加和更换） =====================

def _audit_upgrade(entries: list) -> None:
    """升级变更审计日志（data/logs/model_upgrade.log，一行一条 JSON）"""
    import json as _j
    from datetime import datetime as _dt
    try:
        log_dir = os.path.join(root_path(), "data", "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "model_upgrade.log"), "a", encoding="utf-8") as f:
            f.write(_j.dumps({"time": _dt.now().isoformat(timespec="seconds"),
                              "upgrades": entries}, ensure_ascii=False) + "\n")
    except OSError:
        pass


@router.get("/models/upgrade-plan")
async def model_upgrade_plan(request: Request):
    """自动检查更新：在用模型/语音配置 vs 升级知识表 → 待升级清单 + 可添加新模型"""
    require_admin(request)
    from config.settings import AGENT_MODEL_MAP, VOICE_CONFIG
    from yuanai_core.pure.model_upgrades import (
        plan_model_upgrades, plan_new_models, plan_voice_upgrades)
    data = _read_models_file()
    effective = dict(AGENT_MODEL_MAP)
    effective.update(data.get("_agent_models") or {})
    return {
        "model_upgrades": plan_model_upgrades(effective),
        "voice_upgrades": plan_voice_upgrades(dict(VOICE_CONFIG)),
        "available": plan_new_models(data),
    }


@router.post("/models/upgrade")
async def model_upgrade_apply(request: Request):
    """确认后自动更换：加新模型 + 切分配 + 移旧模型 + 语音配置切换，热更新 + 审计"""
    require_admin(request)
    from config.settings import AGENT_MODEL_MAP, reload_agent_models, reload_voice_config
    from yuanai_core.pure.model_upgrades import (
        plan_model_upgrades, plan_voice_upgrades, provider_of)
    data = _read_models_file()
    agent_models = dict(data.get("_agent_models") or {})
    effective = dict(AGENT_MODEL_MAP)
    effective.update(agent_models)

    applied = []
    for p in plan_model_upgrades(effective):
        old, new, label = p["old"], p["new"], p["label"]
        if new not in data:
            data[new] = {"label": label, "provider": provider_of(new)}
        for k in p["used_by"]:
            agent_models[k] = new          # 显式固化新分配（防默认表回退）
        if old in data:
            del data[old]                  # 旧模型登记移除
        applied.append(p)

    voice_applied = []
    for p in plan_voice_upgrades(dict(data.get("_voice_config") or {})):
        vc = dict(data.get("_voice_config") or {})
        vc[p["key"]] = p["new"]
        data["_voice_config"] = vc
        voice_applied.append(p)

    if agent_models:
        data["_agent_models"] = agent_models
    _write_models_file(data)
    reload_agent_models()
    reload_voice_config()
    from config.settings import _load_models, MODELS
    MODELS.clear(); MODELS.update(_load_models())
    _audit_upgrade(applied + voice_applied)
    return {"ok": True, "model_upgrades": applied, "voice_upgrades": voice_applied}


# ===================== 语音配置（合成模型/音色/资源，易淘汰项可换） =====================

_VOICE_CONFIG_KEYS = ("tts_model", "tts_voice", "tts_voice_bot", "asr_resource", "tts_resource")


class VoiceConfigUpdate(BaseModel):
    voice_config: dict


@router.get("/voice-config")
async def get_voice_config(request: Request):
    """语音配置表（当前生效值，含默认）"""
    require_admin(request)
    from config.settings import VOICE_CONFIG
    return {"voice_config": dict(VOICE_CONFIG)}


@router.put("/voice-config")
async def update_voice_config(req: VoiceConfigUpdate, request: Request):
    """更新语音配置：写 models.json _voice_config + 热更新（无需重启）"""
    require_admin(request)
    incoming = req.voice_config or {}
    for k, v in incoming.items():
        if k not in _VOICE_CONFIG_KEYS:
            raise HTTPException(status_code=400, detail=f"未知语音配置项: {k}")
        if not isinstance(v, str) or not v or len(v) > 200:
            raise HTTPException(status_code=400, detail=f"配置值非法: {k}")
    data = _read_models_file()
    merged = dict(data.get("_voice_config") or {})
    merged.update(incoming)
    data["_voice_config"] = merged
    _write_models_file(data)
    from config.settings import reload_voice_config
    reload_voice_config()
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
