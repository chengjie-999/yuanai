"""
知识库管理 API — 支持私有/共享
"""
import os
import re
import json
import shutil
import zipfile
import tempfile
import logging
from fastapi import APIRouter, Request, UploadFile, File, HTTPException, Query
from pydantic import BaseModel

from yuanai_core.rag import (
    _parse_mindmap_md,
    _flatten_tree,
    _chunk_text,
    remove_source,
    add_source_chunks,
    get_source_stats,
    build_knowledge_base,
    search_knowledge,
    AIPROMPT_DIR,
    SPEC_FILE_PATH,
    STEPS_FILE_PATH,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class SourceInfo(BaseModel):
    source: str
    chunks: int
    images: int


class SourceItem(BaseModel):
    source: str
    chunks: int
    images: int
    visibility: str  # "shared" | "private"


# ====================== 辅助 ======================
def _get_user_id(request: Request) -> int:
    uid = getattr(request.state, "user_id", 0)
    return int(uid) if uid else 0


def _process_md_folder(folder_path: str, source_name: str, user_id: int) -> dict:
    md_files = [f for f in os.listdir(folder_path) if f.endswith(".md")]
    if not md_files:
        return {"source": source_name, "chunks": 0, "images": 0, "error": "无 .md 文件"}

    md_path = os.path.join(folder_path, md_files[0])
    tree = _parse_mindmap_md(md_path)
    chunks = _flatten_tree(tree, folder=source_name, user_id=user_id)

    if not chunks:
        return {"source": source_name, "chunks": 0, "images": 0, "error": "解析为空"}

    img_count = len([f for f in os.listdir(folder_path) if f.endswith(".png")])

    removed = remove_source(source_name, user_id=user_id)
    if removed:
        logger.info(f"  删除旧数据: {removed} 条")

    added = add_source_chunks(chunks)
    return {"source": source_name, "chunks": added, "images": img_count}


# ====================== 接口 ======================
@router.get("/sources")
def list_sources(request: Request):
    """列出当前用户可访问的知识源（共享 + 自己的私有）"""
    user_id = _get_user_id(request)
    all_stats = get_source_stats()

    # 区分共享和私有（Milvus 不存储 visibility 字段，用 user_id 判断）
    result = []
    for s in all_stats:
        src = s["source"]
        # user_id=0 的是共享，>0 的是私有
        is_shared = s.get("user_id", 0) == 0
        if is_shared or s.get("user_id") == user_id:
            result.append({
                "source": src,
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
    tag = "共享" if visibility == "shared" else f"私有(uid={user_id})"

    tmp_dir = tempfile.mkdtemp(prefix="kb_upload_")
    zip_path = os.path.join(tmp_dir, file.filename)

    try:
        content = await file.read()
        with open(zip_path, "wb") as f:
            f.write(content)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)
        os.remove(zip_path)

        results = []
        for dirpath, dirnames, filenames in os.walk(tmp_dir):
            md_files = [f for f in filenames if f.endswith(".md")]
            if not md_files:
                continue

            for md_file in md_files:
                md_path = os.path.join(dirpath, md_file)
                parent_dir = os.path.basename(dirpath)
                md_stem = os.path.splitext(md_file)[0]
                source = parent_dir if parent_dir == md_stem else f"{parent_dir}/{md_stem}"

                # 私有知识库：source 名前加用户前缀避免冲突
                if actual_user_id != 0:
                    source = f"u{user_id}_{source}"

                target_dir = os.path.join(AIPROMPT_DIR, source)
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                os.makedirs(target_dir, exist_ok=True)

                shutil.copy2(md_path, os.path.join(target_dir, md_file))
                for f in filenames:
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
                        img_src = os.path.join(dirpath, f)
                        shutil.copy2(img_src, os.path.join(target_dir, f))

                result = _process_md_folder(target_dir, source, user_id=actual_user_id)
                result["visibility"] = visibility
                results.append(result)
                logger.info(f"  📄 [{tag}] {source}: {result.get('chunks', 0)} chunks")

        if not results:
            return {"ok": False, "message": "压缩包中未找到 .md 文件", "sources": []}

        return {
            "ok": True,
            "message": f"成功导入 {len(results)} 个知识源（{tag}）",
            "sources": [SourceInfo(**r) for r in results],
        }

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="无效的 ZIP 文件")
    except Exception as e:
        logger.exception("上传知识库失败")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.delete("/{source:path}")
def delete_source(request: Request, source: str):
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
        count = remove_source(source, user_id=owner_id)
    else:
        # 共享知识源，仅 admin 可删
        from api.v1.middleware import require_admin
        require_admin(request)
        count = remove_source(source)

    if count == 0:
        raise HTTPException(status_code=404, detail=f"知识源不存在: {source}")

    folder = os.path.join(AIPROMPT_DIR, source)
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)
    return {"ok": True, "deleted": count, "source": source}


@router.post("/rebuild")
def rebuild(request: Request):
    """全量重建知识库（admin）"""
    from api.v1.middleware import require_admin
    require_admin(request)
    build_knowledge_base(force_rebuild=True)
    return {"ok": True, "sources": get_source_stats()}


@router.get("/search")
def search(request: Request, q: str = Query(..., description="检索关键词")):
    """检索知识库（自动过滤：共享 + 自己的私有）"""
    user_id = _get_user_id(request)
    result = search_knowledge(q, user_id=user_id)
    return {"query": q, "results": result}
