# -*- coding: utf-8 -*-
"""更新公告（2026-10-31 用户拍板：网站部署更新与本地 Agent 更新各发一条公告）

存储：data/announcements.json（云端工作目录，与 versions.json 同模式）。
来源：
- auto-deploy：后端启动时检测 git HEAD 变化 → 自动发「平台已更新」公告（site）
- auto-agent：后台上传 Agent 新版本成功 → 自动发「新版本已发布」公告（agent）
- manual：管理员在后台「设置 → 更新公告」卡手动发布
前端：聊天页顶部公告条（最新未读）+ 详情面板（全部公告）；已读状态
localStorage 记忆。管理员管理：后台设置页发布/删除。
"""
import json
import os
import threading
import uuid
from datetime import datetime

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request

from utils.data_path import root_path

router = APIRouter(tags=["announcements"])

_MAX_ANNOUNCEMENTS = 50
_LOCK = threading.Lock()


def _ann_file() -> str:
    return os.path.join(root_path(), "data", "announcements.json")


def _load() -> list:
    path = _ann_file()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def _save(items: list) -> None:
    os.makedirs(os.path.dirname(_ann_file()), exist_ok=True)
    tmp = _ann_file() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _ann_file())


def add_announcement(title: str, content: str, kind: str = "site",
                     version: str = "") -> dict:
    """发布一条公告（内部调用：部署钩子/Agent 上传钩子/管理端点）"""
    with _LOCK:
        items = _load()
        entry = {
            "id": uuid.uuid4().hex[:12],
            "title": title[:100],
            "content": content[:2000],
            "kind": kind,  # site / agent
            "version": version[:32],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        items = [entry] + items
        items = items[:_MAX_ANNOUNCEMENTS]
        _save(items)
        return entry


def auto_deploy_announcement() -> None:
    """部署自动公告：后端启动时检测 git HEAD 变化（仅 git 仓库环境生效）"""
    try:
        import subprocess
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root_path(),
            capture_output=True, text=True, timeout=10).stdout.strip()
        if not head:
            return
        state_path = os.path.join(root_path(), "data", "deploy_state.json")
        last = ""
        if os.path.isfile(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    last = json.load(f).get("last_commit", "")
            except Exception:
                pass
        if last == head:
            return
        # 注意：add_announcement 内部自持 _LOCK——此处不得再包一层（非重入锁会死锁）
        add_announcement(
            f"平台已更新（{head[:8]}）",
            f"小元AI 服务已部署更新至 {head[:8]}，新功能与修复已上线。",
            kind="site", version=head[:8])
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path + ".tmp", "w", encoding="utf-8") as f:
            json.dump({"last_commit": head, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, f)
        os.replace(state_path + ".tmp", state_path)
    except Exception:
        pass  # 部署公告失败不影响启动


class AnnouncementBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=2000)
    kind: str = Field("site", pattern="^(site|agent)$")


@router.get("/api/v1/announcements")
async def list_announcements(limit: int = 20):
    """公告列表（登录可见）：新→旧"""
    return _load()[: max(1, min(limit, _MAX_ANNOUNCEMENTS))]


@router.post("/api/v1/admin/announcements")
async def publish_announcement(body: AnnouncementBody, request: Request):
    """管理员手动发布公告（2026-10-31）"""
    from api.v1.middleware import require_admin
    require_admin(request)
    return {"ok": True, "announcement": add_announcement(body.title, body.content, body.kind)}


@router.delete("/api/v1/admin/announcements/{ann_id}")
async def delete_announcement(ann_id: str, request: Request):
    """管理员删除公告（2026-10-31）"""
    from api.v1.middleware import require_admin
    require_admin(request)
    with _LOCK:
        items = _load()
        remaining = [a for a in items if a.get("id") != ann_id]
        if len(remaining) == len(items):
            raise HTTPException(status_code=404, detail="公告不存在")
        _save(remaining)
    return {"ok": True, "deleted": ann_id}
