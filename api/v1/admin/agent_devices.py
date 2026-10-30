"""后台管理 — Agent 维度：安装码/设备绑定/安装包多版本管理/长令牌"""

import os
import re
import json
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from db.session import get_db
from api.v1.middleware import require_admin
from utils.data_path import root_path

router = APIRouter(tags=["admin"])  # 无 prefix：由主 router 统一加 /admin

# ---- Agent 版本清单（2026-10-30 多版本保留：上传不再覆盖，全部留存可回退） ----

_VERSION_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,32}$")  # 版本号白名单（防路径穿越/URL 安全）


def _downloads_dir() -> str:
    d = os.path.join(root_path(), "downloads")
    os.makedirs(d, exist_ok=True)
    return d


def _versions_dir() -> str:
    d = os.path.join(_downloads_dir(), "versions")
    os.makedirs(d, exist_ok=True)
    return d


def _load_versions() -> dict:
    """versions.json 清单：{default_version, versions:[{version,filename,size,sha256,uploaded_at,note}]}"""
    path = os.path.join(_downloads_dir(), "versions.json")
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("versions"), list):
                    return data
        except Exception:
            pass
    return {"default_version": "", "versions": []}


def _save_versions(data: dict) -> None:
    with open(os.path.join(_downloads_dir(), "versions.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _sync_version_json(data: dict) -> None:
    """同步兼容 version.json（客户端自动更新读取）：指向默认版本的
    文件与 hash——客户端零改动。发布顺序纪律保持：先后端（含 sha256）再推 exe。"""
    default = next((v for v in data["versions"] if v["version"] == data.get("default_version")), None)
    if not default and data["versions"]:
        default = data["versions"][-1]  # 未指定默认 → 最新上传
    if not default:
        return
    with open(os.path.join(_downloads_dir(), "version.json"), "w", encoding="utf-8") as f:
        json.dump({
            "version": default["version"],
            "exe": f"/downloads/versions/{default['filename']}",
            "size": default["size"],
            "sha256": default["sha256"],
            "min_version": default["version"],
        }, f, ensure_ascii=False, indent=2)


class AgentTokenRequest(BaseModel):
    user_id: int
    expires_days: float = 180


class AgentCodeGen(BaseModel):
    count: int = 1


class AgentBindRequest(BaseModel):
    agent_id: int
    user_id: int


class AgentFreezeRequest(BaseModel):
    agent_id: int
    enabled: int


@router.post("/agent-token")
async def mint_agent_token(req: AgentTokenRequest, request: Request):
    """为本地 Agent 桥接签发长生命周期 JWT（仅 admin；S3.4 上限收敛为 90 天，
    配合 token_version 吊销：/admin/users/revoke-tokens 可立即作废）"""
    require_admin(request)
    if not 1 <= req.expires_days <= 90:
        raise HTTPException(status_code=400, detail="expires_days 必须在 1-90 天之间")
    from db.session import User
    db = get_db()
    with db.session() as sess:
        user = sess.query(User).filter_by(id=req.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        from api.v1.auth.utils import create_token
        token = create_token(user.id, user.role or "user", user.username or "",
                             expires_days=req.expires_days)
        return {"token": token, "user_id": user.id, "expires_days": req.expires_days}
@router.post("/agent-exe-upload")
async def upload_agent_exe(request: Request, version: str = Form(""), note: str = Form(""),
                           file: UploadFile = File(...)):
    """上传本地 Agent 安装包（仅 admin）——多版本保留（2026-10-30）：
    写入 downloads/versions/yuanai-agent-v{version}.exe 并追加 versions.json 清单，
    不再覆盖旧版本；同版本号上传 = 覆盖该版本（修正重新打包）。
    version.json 同步指向默认版本（客户端自动更新零改动）。
    命名与本地打包脚本 scripts/build_agent.py 产物一致（统一规范）。"""
    require_admin(request)
    version = version.strip() or datetime.now().strftime("%Y%m%d-%H%M%S")
    if not _VERSION_NAME_RE.match(version):
        raise HTTPException(status_code=400, detail="版本号仅限字母/数字/._-（≤32 字符）")
    if not (file.filename or "").lower().endswith(".exe"):
        raise HTTPException(status_code=400, detail="仅支持 .exe 安装包")

    exe_path = os.path.join(_versions_dir(), f"yuanai-agent-v{version}.exe")
    tmp_path = exe_path + ".uploading"

    # 流式分块写入（200MB 级文件不占内存）+ 同步计算 sha256（S1.7，不二次读盘）
    import hashlib
    size = 0
    hasher = hashlib.sha256()
    try:
        with open(tmp_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
                out.write(chunk)
                size += len(chunk)
                if size > 500 * 1024 * 1024:
                    raise HTTPException(status_code=400, detail="安装包超过 500MB 上限")
        if size == 0:
            raise HTTPException(status_code=400, detail="文件为空")

        os.replace(tmp_path, exe_path)
        data = _load_versions()
        entry = {"version": version, "filename": f"yuanai-agent-v{version}.exe",
                 "size": size, "sha256": hasher.hexdigest(),
                 "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "note": (note or "")[:200]}
        data["versions"] = [v for v in data["versions"] if v["version"] != version] + [entry]
        if not data.get("default_version"):
            data["default_version"] = version
        _save_versions(data)
        _sync_version_json(data)
        return {"ok": True, "version": version, "size": size,
                "sha256": hasher.hexdigest()}
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


@router.get("/agent-versions")
async def list_agent_versions(request: Request):
    """版本清单（仅 admin）：含默认标记"""
    require_admin(request)
    data = _load_versions()
    return {"default_version": data.get("default_version", ""), "versions": data["versions"]}


class SetDefaultVersionBody(BaseModel):
    version: str


@router.post("/agent-versions/default")
async def set_default_version(body: SetDefaultVersionBody, request: Request):
    """指定默认下载版本（仅 admin）——同步 version.json 供客户端自动更新"""
    require_admin(request)
    data = _load_versions()
    if not any(v["version"] == body.version for v in data["versions"]):
        raise HTTPException(status_code=404, detail="版本不存在")
    data["default_version"] = body.version
    _save_versions(data)
    _sync_version_json(data)
    return {"ok": True, "default_version": body.version}


@router.delete("/agent-versions/{version}")
async def delete_agent_version(version: str, request: Request):
    """删除某个版本（仅 admin）：默认版本不可删（先改默认再删）"""
    require_admin(request)
    data = _load_versions()
    if data.get("default_version") == version:
        raise HTTPException(status_code=400, detail="默认版本不可删除，请先指定新的默认版本")
    entry = next((v for v in data["versions"] if v["version"] == version), None)
    if not entry:
        raise HTTPException(status_code=404, detail="版本不存在")
    data["versions"] = [v for v in data["versions"] if v["version"] != version]
    _save_versions(data)
    try:
        os.remove(os.path.join(_versions_dir(), entry["filename"]))
    except OSError:
        pass
    return {"ok": True, "deleted": version}


@router.post("/agent-codes")
async def gen_agent_codes(req: AgentCodeGen, request: Request):
    """批量生成 Agent 安装码（未注册状态，安装码即本机注册凭证）"""
    require_admin(request)
    if not 1 <= req.count <= 50:
        raise HTTPException(status_code=400, detail="count 必须在 1-50 之间")
    import secrets as _secrets
    from db.session import AgentDevice
    db = get_db()
    with db.session() as sess:
        codes = []
        for _ in range(req.count):
            code = "YUAN-" + "-".join(_secrets.token_hex(2).upper() for _ in range(3))
            sess.add(AgentDevice(install_code=code, agent_secret=""))
            codes.append(code)
        sess.commit()
        return {"codes": codes}
@router.get("/agent-devices")
async def list_agent_devices(request: Request):
    """设备列表：注册状态、绑定用户、在线状态、最后在线时间"""
    require_admin(request)
    from db.session import AgentDevice, User
    from api.v1.agent.router import _agents
    db = get_db()
    with db.session() as sess:
        devices = sess.query(AgentDevice).order_by(AgentDevice.id.desc()).all()
        users = {u.id: u.username for u in sess.query(User).all()}
        result = []
        for d in devices:
            result.append({
                "agent_id": d.id,
                "install_code": d.install_code,
                "registered": bool(d.agent_secret),
                "machine_name": d.machine_name or "",
                "user_id": d.user_id,
                "username": users.get(d.user_id, "") if d.user_id else "",
                "enabled": d.enabled == 1,
                "online": str(d.id) in _agents,
                "last_seen": str(d.last_seen)[:19] if d.last_seen else "",
                "create_time": str(d.create_time)[:19] if d.create_time else "",
            })
        return result
@router.post("/agent-bind")
async def bind_agent_device(req: AgentBindRequest, request: Request):
    """一对一绑定：设备 ↔ 云端用户（admin 操作；双方均不能已绑定）"""
    require_admin(request)
    from db.session import AgentDevice, User
    db = get_db()
    with db.session() as sess:
        dev = sess.query(AgentDevice).filter_by(id=req.agent_id).first()
        if not dev:
            raise HTTPException(status_code=404, detail="设备不存在")
        user = sess.query(User).filter_by(id=req.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if dev.user_id and dev.user_id != req.user_id:
            raise HTTPException(status_code=400, detail=f"该设备已绑定用户 {dev.user_id}，请先解绑")
        other = sess.query(AgentDevice).filter(AgentDevice.user_id == req.user_id,
                                               AgentDevice.id != req.agent_id).first()
        if other:
            raise HTTPException(status_code=400, detail=f"该用户已绑定设备 {other.id}（一对一）")
        dev.user_id = req.user_id
        sess.commit()
        from api.v1.agent.router import invalidate_bind_cache
        invalidate_bind_cache(req.user_id)
        return {"ok": True, "agent_id": dev.id, "user_id": req.user_id}
@router.post("/agent-unbind")
async def unbind_agent_device(req: AgentBindRequest, request: Request):
    """解绑设备（仅传 agent_id 即可，user_id 忽略）"""
    require_admin(request)
    from db.session import AgentDevice
    db = get_db()
    with db.session() as sess:
        dev = sess.query(AgentDevice).filter_by(id=req.agent_id).first()
        if not dev:
            raise HTTPException(status_code=404, detail="设备不存在")
        old_user = dev.user_id
        dev.user_id = None
        sess.commit()
        if old_user:
            from api.v1.agent.router import invalidate_bind_cache
            invalidate_bind_cache(old_user)
        return {"ok": True, "agent_id": dev.id}
@router.post("/agent-freeze")
async def freeze_agent_device(req: AgentFreezeRequest, request: Request):
    """冻结/解冻设备（冻结后 WS 连接被拒绝）"""
    require_admin(request)
    from db.session import AgentDevice
    db = get_db()
    with db.session() as sess:
        dev = sess.query(AgentDevice).filter_by(id=req.agent_id).first()
        if not dev:
            raise HTTPException(status_code=404, detail="设备不存在")
        dev.enabled = 1 if req.enabled else 0
        sess.commit()
        return {"ok": True, "agent_id": dev.id, "enabled": dev.enabled == 1}