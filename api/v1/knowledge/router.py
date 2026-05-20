"""
知识库管理 API — 支持私有/共享
耗时操作（ZIP 解压、MD 解析、Embedding、Milvus 写入）放入线程池，
通过 asyncio.shield 防止客户端断开取消任务。
"""
import os
import re
import json
import asyncio
import shutil
import zipfile
import tempfile
import logging
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Request, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from yuanai_core.rag import (
    _parse_mindmap_md,
    _flatten_tree,
    remove_source,
    add_source_chunks,
    get_source_stats,
    build_knowledge_base,
    search_knowledge,
    AIPROMPT_DIR,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

# 知识库专用线程池（最多 2 个并发任务，避免同时上传 + 重建打满资源）
_kb_executor = ThreadPoolExecutor(max_workers=2)


class SourceInfo(BaseModel):
    source: str
    chunks: int
    images: int


# ====================== 辅助 ======================
def _get_user_id(request: Request) -> int:
    uid = getattr(request.state, "user_id", 0)
    return int(uid) if uid else 0


def _find_and_process_mds(
    extract_dir: str, actual_user_id: int, visibility: str, user_id: int, tag: str
) -> list[dict]:
    """在解压目录中递归查找 .md 并解析入库（在线程池中运行）"""
    results = []
    for dirpath, dirnames, filenames in os.walk(extract_dir):
        md_files = [f for f in filenames if f.endswith(".md")]
        if not md_files:
            continue

        for md_file in md_files:
            md_path = os.path.join(dirpath, md_file)
            parent_dir = os.path.basename(dirpath)
            md_stem = os.path.splitext(md_file)[0]
            source = parent_dir if parent_dir == md_stem else f"{parent_dir}/{md_stem}"

            if actual_user_id != 0:
                source = f"u{user_id}_{source}"

            # 复制文件到 aiprompt
            target_dir = os.path.join(AIPROMPT_DIR, source)
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            os.makedirs(target_dir, exist_ok=True)

            shutil.copy2(md_path, os.path.join(target_dir, md_file))
            for f in filenames:
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
                    img_src = os.path.join(dirpath, f)
                    shutil.copy2(img_src, os.path.join(target_dir, f))

            # 解析 → 生成 embedding → 入库
            md_real = os.path.join(target_dir, md_file)
            tree = _parse_mindmap_md(md_real)
            chunks = _flatten_tree(tree, folder=source, user_id=actual_user_id)

            if not chunks:
                results.append({"source": source, "chunks": 0, "images": 0, "error": "解析为空", "visibility": visibility})
                continue

            img_count = len([f for f in os.listdir(target_dir) if f.endswith(".png")])

            removed = remove_source(source, user_id=actual_user_id)
            if removed:
                logger.info(f"  删除旧数据 [{source}]: {removed} 条")

            added = add_source_chunks(chunks)
            logger.info(f"  📄 [{tag}] {source}: {added} chunks")
            results.append({"source": source, "chunks": added, "images": img_count, "visibility": visibility})

    return results


def _run_upload(content: bytes, filename: str, actual_user_id: int, visibility: str, user_id: int) -> dict:
    """同步执行上传全流程（在线程池中运行）"""
    tag = "共享" if visibility == "shared" else f"私有(uid={user_id})"
    tmp_dir = tempfile.mkdtemp(prefix="kb_upload_")
    zip_path = os.path.join(tmp_dir, filename)

    try:
        with open(zip_path, "wb") as f:
            f.write(content)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)
        os.remove(zip_path)

        results = _find_and_process_mds(tmp_dir, actual_user_id, visibility, user_id, tag)

        if not results:
            return {"ok": False, "message": "压缩包中未找到 .md 文件", "sources": []}

        return {
            "ok": True,
            "message": f"成功导入 {len(results)} 个知识源（{tag}）",
            "sources": [SourceInfo(**r) for r in results],
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ====================== 接口 ======================
@router.get("/sources")
async def list_sources(request: Request):
    """列出当前用户可访问的知识源（共享 + 自己的私有）"""
    user_id = _get_user_id(request)

    loop = asyncio.get_running_loop()
    all_stats = await loop.run_in_executor(_kb_executor, get_source_stats)

    result = []
    for s in all_stats:
        is_shared = s.get("user_id", 0) == 0
        if is_shared or s.get("user_id") == user_id:
            result.append({
                "source": s["source"],
                "chunks": s["chunks"],
                "images": s["images"],
                "visibility": "shared" if is_shared else "private",
            })
    return result


@router.post("/upload")
async def upload_knowledge(
    request: Request,
    file: UploadFile = File(...),
    visibility: str = Query("shared", regex="^(shared|private)$"),
):
    """上传 ZIP 压缩包，visibility=shared 共享 / private 私有"""
    user_id = _get_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="仅支持 .zip 压缩包")

    actual_user_id = 0 if visibility == "shared" else user_id
    content = await file.read()

    loop = asyncio.get_running_loop()
    try:
        result = await asyncio.shield(
            loop.run_in_executor(
                _kb_executor,
                _run_upload,
                content, file.filename, actual_user_id, visibility, user_id,
            )
        )
        return result
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="无效的 ZIP 文件")
    except Exception as e:
        logger.exception("上传知识库失败")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@router.delete("/{source:path}")
async def delete_source(request: Request, source: str):
    """删除知识源（私有只能删自己的，共享需要 admin）"""
    user_id = _get_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    # 私有知识源（source 名以 u{uid}_ 开头）只能自己删
    match = re.match(r'^u(\d+)_', source)
    if match:
        owner_id = int(match.group(1))
        if owner_id != user_id:
            raise HTTPException(status_code=403, detail="只能删除自己的私有知识库")

        loop = asyncio.get_running_loop()
        count = await loop.run_in_executor(_kb_executor, remove_source, source, owner_id)
    else:
        from api.v1.middleware import require_admin
        require_admin(request)

        loop = asyncio.get_running_loop()
        count = await loop.run_in_executor(_kb_executor, remove_source, source)

    if count == 0:
        raise HTTPException(status_code=404, detail=f"知识源不存在: {source}")

    folder = os.path.join(AIPROMPT_DIR, source)
    if os.path.isdir(folder):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(_kb_executor, shutil.rmtree, folder, True)
    return {"ok": True, "deleted": count, "source": source}


@router.post("/rebuild")
async def rebuild(request: Request):
    """全量重建知识库（admin）"""
    from api.v1.middleware import require_admin
    require_admin(request)

    loop = asyncio.get_running_loop()
    try:
        await asyncio.shield(
            loop.run_in_executor(_kb_executor, build_knowledge_base, True)
        )
        stats = await loop.run_in_executor(_kb_executor, get_source_stats)
        return {"ok": True, "sources": stats}
    except Exception as e:
        logger.exception("知识库重建失败")
        raise HTTPException(status_code=500, detail=f"重建失败: {str(e)}")


@router.get("/img/{source}/{filename:path}")
async def serve_kb_image(source: str, filename: str):
    """提供知识库图片（公开访问）"""
    img_path = os.path.join(AIPROMPT_DIR, source, filename)
    if not os.path.isfile(img_path):
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(img_path)


@router.get("/search")
async def search(request: Request, q: str = Query(..., description="检索关键词")):
    """检索知识库（自动过滤：共享 + 自己的私有）"""
    user_id = _get_user_id(request)
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(_kb_executor, search_knowledge, q, 5, None, user_id)
    return {"query": q, "results": result}
