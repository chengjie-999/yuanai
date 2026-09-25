"""后台管理 — Agent 维度：安装码/设备绑定/安装包上传/长令牌"""

import os
import json
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from db.session import get_db
from api.v1.middleware import require_admin
from utils.data_path import root_path

router = APIRouter(tags=["admin"])  # 无 prefix：由主 router 统一加 /admin


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
    """为本地 Agent 桥接签发长生命周期 JWT（仅 admin；默认 180 天，上限 365 天）"""
    require_admin(request)
    if not 1 <= req.expires_days <= 365:
        raise HTTPException(status_code=400, detail="expires_days 必须在 1-365 天之间")
    from db.session import User
    db = get_db()
    sess = db.Session()
    try:
        user = sess.query(User).filter_by(id=req.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        from api.v1.auth.utils import create_token
        token = create_token(user.id, user.role or "user", user.username or "",
                             expires_days=req.expires_days)
        return {"token": token, "user_id": user.id, "expires_days": req.expires_days}
    finally:
        sess.close()


@router.post("/agent-exe-upload")
async def upload_agent_exe(request: Request, version: str = Form(""), file: UploadFile = File(...)):
    """上传本地 Agent 安装包（仅 admin）：写入 downloads/yuanai-agent.exe 并更新 version.json。
    发布流程：打包 → 网页拖拽上传 → 所有客户端按 version.json 自动检查更新。
    版本号留空时自动按上传时间生成（客户端比对不同即提示更新）。"""
    require_admin(request)
    version = version.strip() or datetime.now().strftime("%Y%m%d-%H%M%S")
    if not (file.filename or "").lower().endswith(".exe"):
        raise HTTPException(status_code=400, detail="仅支持 .exe 安装包")

    downloads_dir = os.path.join(root_path(), "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    exe_path = os.path.join(downloads_dir, "yuanai-agent.exe")
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

        # 原子替换 + 更新版本信息（version.json 供客户端自动更新检查；
        # sha256 为客户端下载校验必需——发布顺序：先后端（含 sha256）再推新客户端）
        os.replace(tmp_path, exe_path)
        with open(os.path.join(downloads_dir, "version.json"), "w", encoding="utf-8") as f:
            json.dump({
                "version": version,
                "exe": "/downloads/yuanai-agent.exe",
                "size": size,
                "sha256": hasher.hexdigest(),
                "min_version": version,
            }, f, ensure_ascii=False, indent=2)
        return {"ok": True, "version": version, "size": size,
                "sha256": hasher.hexdigest()}
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


@router.post("/agent-codes")
async def gen_agent_codes(req: AgentCodeGen, request: Request):
    """批量生成 Agent 安装码（未注册状态，安装码即本机注册凭证）"""
    require_admin(request)
    if not 1 <= req.count <= 50:
        raise HTTPException(status_code=400, detail="count 必须在 1-50 之间")
    import secrets as _secrets
    from db.session import AgentDevice
    db = get_db()
    sess = db.Session()
    try:
        codes = []
        for _ in range(req.count):
            code = "YUAN-" + "-".join(_secrets.token_hex(2).upper() for _ in range(3))
            sess.add(AgentDevice(install_code=code, agent_secret=""))
            codes.append(code)
        sess.commit()
        return {"codes": codes}
    finally:
        sess.close()


@router.get("/agent-devices")
async def list_agent_devices(request: Request):
    """设备列表：注册状态、绑定用户、在线状态、最后在线时间"""
    require_admin(request)
    from db.session import AgentDevice, User
    from api.v1.agent.router import _agents
    db = get_db()
    sess = db.Session()
    try:
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
    finally:
        sess.close()


@router.post("/agent-bind")
async def bind_agent_device(req: AgentBindRequest, request: Request):
    """一对一绑定：设备 ↔ 云端用户（admin 操作；双方均不能已绑定）"""
    require_admin(request)
    from db.session import AgentDevice, User
    db = get_db()
    sess = db.Session()
    try:
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
    finally:
        sess.close()


@router.post("/agent-unbind")
async def unbind_agent_device(req: AgentBindRequest, request: Request):
    """解绑设备（仅传 agent_id 即可，user_id 忽略）"""
    require_admin(request)
    from db.session import AgentDevice
    db = get_db()
    sess = db.Session()
    try:
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
    finally:
        sess.close()


@router.post("/agent-freeze")
async def freeze_agent_device(req: AgentFreezeRequest, request: Request):
    """冻结/解冻设备（冻结后 WS 连接被拒绝）"""
    require_admin(request)
    from db.session import AgentDevice
    db = get_db()
    sess = db.Session()
    try:
        dev = sess.query(AgentDevice).filter_by(id=req.agent_id).first()
        if not dev:
            raise HTTPException(status_code=404, detail="设备不存在")
        dev.enabled = 1 if req.enabled else 0
        sess.commit()
        return {"ok": True, "agent_id": dev.id, "enabled": dev.enabled == 1}
    finally:
        sess.close()
