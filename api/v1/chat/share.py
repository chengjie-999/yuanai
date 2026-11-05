# -*- coding: utf-8 -*-
"""V1-4 会话静态产物化 + 分享（2026-11-06，用户拍板：主动分享才公开）

用户点「分享对话」→ POST /chat/share/{session_id}：服务端把完整会话渲染为
静态 HTML（标题/正文/时间 + canonical + robots 收录 + C5 AI 标识 + C7 举报
入口）落 data/shares/{session_id}.html → 公开 GET /api/v1/share/{session_id}
（curl 出完整正文、可被抓取）。取消分享 DELETE 删文件即下线。

安全/合规：
- 分享是用户主动动作（默认不公开）；会话归属校验（verify_session_owner）
- C5：页脚「内容由 AI 生成」标识（生成式 AI 内容标识办法硬要求）
- C7：页脚举报入口（平台邮箱 mailto，附会话 id 便于处置）
- HTML 转义（消息内容来自用户/模型，防注入）；无 JS 零依赖自包含
"""
import html as _html
import json
import logging
import os
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from utils.data_path import root_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["share"])

_SHARES_DIR = os.path.join(root_path(), "data", "shares")
_SID_RE = re.compile(r"^[0-9a-zA-Z\-]{8,64}$")


def _shares_dir() -> str:
    return os.path.join(root_path(), "data", "shares")


def _share_path(session_id: str) -> str:
    return os.path.join(_shares_dir(), f"{session_id}.html")


def _strip_meta(content: str) -> str:
    """剥 \x00META\x00 前缀（消息原文字段含工具卡/信封元数据）"""
    if isinstance(content, str) and content.startswith("\x00META\x00"):
        end = content.find("\x00", 6)
        if end > 6:
            content = content[end + 1:]
    return content or ""


def _render_html(title: str, session_id: str, created_at: str, messages: list) -> str:
    """服务端静态 HTML（内联样式自包含；无 JS）"""
    rows = []
    for m in messages:
        role = m.get("role", "user")
        content = _html.escape(_strip_meta(m.get("content", ""))).replace("\n", "<br/>")
        if not content.strip():
            continue
        is_user = role == "user"
        rows.append(
            f'<div class="msg {"user" if is_user else "ai"}">'
            f'<div class="bubble">{content}</div></div>'
        )
    body = "\n".join(rows) if rows else '<p class="empty">该会话暂无内容</p>'
    title_esc = _html.escape(title or "小元AI 对话分享")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_esc} - 小元AI</title>
<meta name="description" content="小元AI 平台用户分享的对话内容">
<meta name="robots" content="index, follow">
<link rel="canonical" href="/api/v1/share/{session_id}">
<meta property="og:title" content="{title_esc}">
<meta property="og:type" content="article">
<meta property="og:description" content="小元AI 对话分享">
<style>
  body {{ font-family: 'PingFang SC','Microsoft YaHei',sans-serif; background:#f1f5f9;
         margin:0; padding:24px 12px; color:#0f172a; }}
  .wrap {{ max-width:720px; margin:0 auto; }}
  header {{ background:#fff; border-radius:12px; padding:20px 24px; margin-bottom:16px;
            border:1px solid #e2e8f0; }}
  h1 {{ font-size:20px; margin:0 0 6px; }}
  .meta {{ font-size:12px; color:#64748b; }}
  .msg {{ display:flex; margin-bottom:10px; }}
  .msg.user {{ justify-content:flex-end; }}
  .msg.ai {{ justify-content:flex-start; }}
  .bubble {{ max-width:85%; padding:10px 14px; border-radius:10px; font-size:14px;
             line-height:1.7; word-break:break-word; }}
  .user .bubble {{ background:#2563eb; color:#fff; border-bottom-right-radius:3px; }}
  .ai .bubble {{ background:#fff; border:1px solid #e2e8f0; border-bottom-left-radius:3px; }}
  .empty {{ text-align:center; color:#64748b; }}
  footer {{ margin-top:24px; padding:16px 24px; background:#fff; border-radius:12px;
            border:1px solid #e2e8f0; font-size:12px; color:#64748b; line-height:1.9; }}
  footer a {{ color:#2563eb; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>{title_esc}</h1>
    <div class="meta">分享于 {_html.escape(created_at)} · 小元AI 平台</div>
  </header>
  {body}
  <footer>
    <div>本页面内容由 <b>AI 生成</b>，可能存在不准确之处，仅供参考。</div>
    <div>如内容涉嫌违规或侵权，请通过
      <a href="mailto:chengjie2017020@163.com?subject=%E4%B8%BE%E6%8A%A5%E5%88%86%E4%BA%AB%E5%86%85%E5%AE%B9%20{_html.escape(session_id)}">举报入口</a>
      联系我们处理（附上本页链接）。</div>
    <div>—— 小元AI</div>
  </footer>
</div>
</body>
</html>
"""


def render_share_html(session_id: str, title: str, created_at: str, messages: list) -> str:
    """渲染分享 HTML（纯函数，测试可注入）"""
    return _render_html(title, session_id, created_at, messages)


@router.post("/chat/share/{session_id}")
async def share_session(session_id: str, request: Request):
    """分享对话：服务端渲染静态 HTML 落盘 → 返回公开链接。分享是用户主动动作。"""
    from api.v1.db_helpers import verify_session_owner
    from api.v1.middleware import get_user_id
    from db.session import get_db
    uid = get_user_id(request)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    if not _SID_RE.match(session_id or ""):
        raise HTTPException(status_code=400, detail="会话 ID 格式不正确")
    db = get_db()
    verify_session_owner(db, session_id, uid)
    msgs = db.get_chats(session_id)
    if not msgs:
        raise HTTPException(status_code=400, detail="会话暂无内容，无法分享")
    title = ""
    try:
        from db.session import ChatSession
        with db.session() as sess:
            row = sess.query(ChatSession).filter_by(session_id=session_id).first()
            if row:
                title = row.title or ""
    except Exception:
        pass
    from yuanai_core.pure.beijing_time import beijing_now
    created = beijing_now().strftime("%Y-%m-%d %H:%M")
    html = render_share_html(session_id, title, created, msgs)
    os.makedirs(_shares_dir(), exist_ok=True)
    tmp = _share_path(session_id) + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(tmp, _share_path(session_id))
    logger.info("会话已分享: sid=%s user=%s", session_id, uid)
    return {"ok": True, "url": f"/api/v1/share/{session_id}"}


@router.delete("/chat/share/{session_id}")
async def unshare_session(session_id: str, request: Request):
    """取消分享：删除静态文件即下线（会话数据不受影响）"""
    from api.v1.db_helpers import verify_session_owner
    from api.v1.middleware import get_user_id
    from db.session import get_db
    uid = get_user_id(request)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    if not _SID_RE.match(session_id or ""):
        raise HTTPException(status_code=400, detail="会话 ID 格式不正确")
    verify_session_owner(get_db(), session_id, uid)
    path = _share_path(session_id)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="该会话未分享")
    os.remove(path)
    return {"ok": True}


@router.get("/share/{session_id}")
async def get_share(session_id: str):
    """公开分享页（静态 HTML；未分享 404）"""
    if not _SID_RE.match(session_id or ""):
        raise HTTPException(status_code=404, detail="分享不存在")
    path = _share_path(session_id)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="分享不存在或已取消")
    return FileResponse(path, media_type="text/html",
                        headers={"Cache-Control": "public, max-age=300"})
