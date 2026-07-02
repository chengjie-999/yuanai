import os
import io
import json
import asyncio
import base64
import logging
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from db.session import get_db
from utils.data_path import root_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data", tags=["data"])

_process_pool = ProcessPoolExecutor(max_workers=1)

DATASETS_DIR = os.path.join(root_path(), "data", "datasets")
ANALYSIS_DIR = os.path.join(root_path(), "data", "analysis")
os.makedirs(DATASETS_DIR, exist_ok=True)
os.makedirs(ANALYSIS_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json"}


def _get_user_id(request: Request) -> int:
    return getattr(request.state, "user_id", None)


def _is_admin(request: Request) -> bool:
    return getattr(request.state, "role", "") == "admin"


def _check_ownership(request: Request, ds: dict):
    """非管理员只能访问自己的数据集"""
    if ds and not _is_admin(request):
        owner_id = ds.get("user_id")
        user_id = _get_user_id(request)
        if owner_id is not None and owner_id != user_id:
            raise HTTPException(status_code=404, detail="not found")


@router.post("/upload")
async def upload_dataset(request: Request, file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"unsupported format: {ext}")

    user_id = _get_user_id(request)
    db = get_db()
    content = await file.read()
    file_size = len(content)

    # dedup: same name + same size → update existing
    from db.session import Dataset
    sess = db.Session()
    existing = None
    try:
        existing = sess.query(Dataset).filter_by(
            name=file.filename, file_size=file_size, user_id=user_id,
        ).first()
    finally:
        sess.close()

    if existing:
        ds_id = existing.id
        fpath = existing.file_path
        with open(fpath, "wb") as f:
            f.write(content)
        # update create_time
        from sqlalchemy.sql import func
        sess2 = db.Session()
        try:
            r = sess2.query(Dataset).filter_by(id=ds_id).first()
            if r:
                r.create_time = func.now()
                sess2.commit()
        finally:
            sess2.close()
        # clear stale analysis cache
        try:
            from db.redis_client import get_redis
            rds = get_redis()
            rds.delete(f"analysis:{ds_id}:basic")
            rds.delete(f"analysis:{ds_id}:full")
            rds.delete(f"analysis_mtime:{ds_id}")
        except Exception:
            pass
        for fn in ("result_basic.json", "result_full.json"):
            cf = os.path.join(ANALYSIS_DIR, str(ds_id), fn)
            if os.path.exists(cf):
                os.remove(cf)
    else:
        ds_id = db.add_dataset(
            name=file.filename, file_path="", file_type=ext.lstrip("."),
            file_size=0, row_count=0, columns_info=[], preview_rows=[],
            user_id=user_id,
        )
        fname = f"{ds_id}_{file.filename}"
        fpath = os.path.join(DATASETS_DIR, fname)
        with open(fpath, "wb") as f:
            f.write(content)
    row_count = 0
    columns_info = []
    preview_rows = []

    try:
        if ext == ".csv":
            import pandas as pd
            df = pd.read_csv(fpath, nrows=100)
        elif ext in (".xlsx", ".xls"):
            import pandas as pd
            df = pd.read_excel(fpath, nrows=100)
        elif ext == ".json":
            import pandas as pd
            df = pd.read_json(fpath)
            if len(df) > 100:
                df = df.head(100)
        else:
            df = None

        if df is not None:
            row_count = len(df) if ext != ".json" else sum(1 for _ in open(fpath, encoding="utf-8"))
            columns_info = [{"name": str(c), "dtype": str(df[c].dtype)} for c in df.columns]
            for c in df.select_dtypes(include=["datetime64", "datetimetz"]).columns:
                df[c] = df[c].astype(str)
            preview_rows = json.loads(df.head(100).fillna("").to_json(orient="records", date_format="iso"))
    except Exception as e:
        logger.warning("parse failed: %s", e)

    if ext in (".csv", ".json") and row_count == 0:
        try:
            row_count = sum(1 for _ in open(fpath, encoding="utf-8")) - 1
        except Exception:
            pass

    from db.session import Dataset
    sess = db.Session()
    try:
        ds = sess.query(Dataset).filter_by(id=ds_id).first()
        if ds:
            ds.file_path = fpath
            ds.file_size = file_size
            ds.row_count = row_count
            ds.columns_info = json.dumps(columns_info, ensure_ascii=False)
            ds.preview_rows = json.dumps(preview_rows, ensure_ascii=False)
            sess.commit()
    finally:
        sess.close()

    return {"id": ds_id, "name": file.filename, "file_type": ext.lstrip("."),
            "file_size": file_size, "row_count": row_count,
            "columns": columns_info, "preview_rows": preview_rows}


@router.get("/datasets")
async def list_datasets(request: Request):
    db = get_db()
    user_id = None if _is_admin(request) else _get_user_id(request)
    return db.get_datasets(user_id=user_id)


@router.get("/dataset/{ds_id}")
async def get_dataset(ds_id: int, request: Request):
    db = get_db()
    ds = db.get_dataset(ds_id)
    _check_ownership(request, ds)
    return ds




@router.get("/analyze/{ds_id}")
async def analyze_dataset_api(ds_id: int, request: Request, force: bool = False, charts: bool = False, cache_only: bool = False):
    db = get_db()
    ds = db.get_dataset(ds_id)
    _check_ownership(request, ds)

    path = ds["file_path"]
    file_mtime = os.path.getmtime(path) if os.path.exists(path) else 0

    KEY_BASIC = f"analysis:{ds_id}:basic"
    KEY_FULL = f"analysis:{ds_id}:full"
    KEY_MTIME = f"analysis_mtime:{ds_id}"
    FILE_BASIC = os.path.join(ANALYSIS_DIR, str(ds_id), "result_basic.json")
    FILE_FULL = os.path.join(ANALYSIS_DIR, str(ds_id), "result_full.json")

    if charts:
        search_keys = [(KEY_FULL, FILE_FULL)]
    else:
        # basic first, then try full (has superset of data)
        search_keys = [(KEY_BASIC, FILE_BASIC), (KEY_FULL, FILE_FULL)]

    if not force:
        for rkey, fkey in search_keys:
            try:
                from db.redis_client import get_redis
                rds = get_redis()
                cached_mtime = rds.get(KEY_MTIME)
                if cached_mtime and int(cached_mtime) >= file_mtime:
                    cached = rds.get(rkey)
                    if cached:
                        return json.loads(cached)
            except Exception:
                pass
            if os.path.exists(fkey) and os.path.getmtime(fkey) >= file_mtime:
                try:
                    with open(fkey, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass

    if cache_only:
        return JSONResponse(content={"cached": False}, status_code=204)

    # run analysis in process pool
    global _process_pool
    try:
        from yuanai_core.pure.analysis import run_analysis
        loop = asyncio.get_running_loop()
        result = await asyncio.shield(
            loop.run_in_executor(_process_pool, run_analysis, ds, ds_id, charts)
        )
    except Exception:
        _process_pool = ProcessPoolExecutor(max_workers=1)
        result = await asyncio.shield(
            loop.run_in_executor(_process_pool, run_analysis, ds, ds_id, charts)
        )

    # cache
    result_json = json.dumps(result, ensure_ascii=False)
    cache_rkey = KEY_FULL if charts else KEY_BASIC
    cache_fkey = FILE_FULL if charts else FILE_BASIC
    try:
        from db.redis_client import get_redis
        rds = get_redis()
        rds.setex(cache_rkey, 86400, result_json)
        rds.setex(KEY_MTIME, 86400, str(int(file_mtime)))
    except Exception as e:
        logger.warning("redis cache failed for #%d: %s", ds_id, e)
    try:
        os.makedirs(os.path.dirname(cache_fkey), exist_ok=True)
        with open(cache_fkey, "w", encoding="utf-8") as f:
            f.write(result_json)
        logger.info("analysis cached for dataset #%d (%s)", ds_id, "full" if charts else "basic")
    except Exception as e:
        logger.warning("file cache failed for #%d: %s", ds_id, e)

    return result


@router.get("/analysis-image/{ds_id}/{name}")
async def serve_analysis_image(ds_id: int, name: str, request: Request):
    db = get_db()
    ds = db.get_dataset(ds_id)
    _check_ownership(request, ds)
    from yuanai_core.pure.analysis import ANALYSIS_DIR
    fpath = os.path.join(ANALYSIS_DIR, str(ds_id), f"{name}.png")
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="not found")
    from fastapi.responses import FileResponse
    return FileResponse(fpath, media_type="image/png")


@router.get("/analysis-html/{ds_id}/{name}")
async def serve_analysis_html(ds_id: int, name: str, request: Request):
    from yuanai_core.pure.analysis import ANALYSIS_DIR
    db = get_db()
    ds = db.get_dataset(ds_id)
    _check_ownership(request, ds)
    fpath = os.path.join(ANALYSIS_DIR, str(ds_id), f"{name}.html")
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="not found")
    from fastapi.responses import HTMLResponse
    with open(fpath, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@router.get("/export/{ds_id}")
async def export_analysis(ds_id: int, request: Request, format: str = "excel"):
    from yuanai_core.pure.analysis import run_analysis
    from yuanai_core.pure.export import export_excel, export_html

    db = get_db()
    ds = db.get_dataset(ds_id)
    _check_ownership(request, ds)

    result = run_analysis(ds, ds_id, charts=True)

    if format == "excel":
        data = export_excel(result)
        from fastapi.responses import Response
        filename = f"{result['name'].rsplit('.', 1)[0]}_分析报告.xlsx"
        return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    elif format == "html":
        html = export_html(result)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html)

    else:
        raise HTTPException(status_code=400, detail="unsupported format")


@router.delete("/dataset/{ds_id}")
async def delete_dataset(ds_id: int, request: Request):
    db = get_db()
    user_id = None if _is_admin(request) else _get_user_id(request)
    ok = db.delete_dataset(ds_id, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="not found or permission denied")
    return {"ok": True}
