# -*- coding: utf-8 -*-
"""README 实时文档服务（2026-10-19 用户拍板：首页 API 文档页与 README 同一文件）

/api-docs 页直接消费仓库根 README.md——改 README 即改页面（后端每次请求读文件，
生产环境 git pull 后自动同步，无需重新构建前端）。相对图片链接
（docs/diagrams/*.svg 等）改写为本服务的资产端点。
"""

import os
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from utils.data_path import root_path

router = APIRouter(tags=["docs"])

_ASSET_DIR = os.path.realpath(os.path.join(root_path(), "docs"))
_ASSET_NAME_RE = re.compile(r"^[A-Za-z0-9_\-./]+$")
_MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
         ".jpeg": "image/jpeg", ".gif": "image/gif", ".md": "text/markdown",
         ".txt": "text/plain", ".html": "text/html"}


@router.get("/api/v1/docs/readme")
async def serve_readme():
    """仓库 README.md 原文（markdown）；相对 docs/ 图片链接改写到资产端点"""
    path = os.path.join(root_path(), "README.md")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="README not found")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # ](docs/diagrams/arch.svg) → ](/api/v1/docs/asset/diagrams/arch.svg)
    content = re.sub(r"\]\(docs/([^)]+)\)", r"](/api/v1/docs/asset/\1)", content)
    return Response(
        content=content, media_type="text/markdown; charset=utf-8",
        headers={"Cache-Control": "no-store"})


@router.get("/api/v1/docs/asset/{asset_path:path}")
async def serve_docs_asset(asset_path: str):
    """docs/ 目录资产（README 内嵌图片）；文件名白名单 + realpath 防越界"""
    if not _ASSET_NAME_RE.match(asset_path) or ".." in asset_path.split("/"):
        raise HTTPException(status_code=400, detail="非法路径")
    full = os.path.realpath(os.path.join(_ASSET_DIR, asset_path))
    if not (full == _ASSET_DIR or full.startswith(_ASSET_DIR + os.sep)):
        raise HTTPException(status_code=403, detail="越界路径")
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="not found")
    ext = os.path.splitext(full)[1].lower()
    with open(full, "rb") as f:
        return Response(content=f.read(), media_type=_MIME.get(ext, "application/octet-stream"),
                        headers={"Cache-Control": "no-store"})
