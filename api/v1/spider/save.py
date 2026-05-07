from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Optional

from spiderlx.core.save.save_data import SavedData

router = APIRouter()


class SaveHTMLParams(BaseModel):
    name: str = Field(..., description="保存文件名")
    data: str = Field(..., description="HTML内容")


class SaveCSVParams(BaseModel):
    name: str = Field(..., description="保存文件名")
    data_list: List[List[str]] = Field(..., description="CSV数据列表")
    columns: Optional[List[str]] = Field(default=None, description="列名")


class SaveExcelParams(BaseModel):
    name: str = Field(..., description="保存文件名")
    data_list: List[List[str]] = Field(..., description="Excel数据列表")


class SaveMysqlParams(BaseModel):
    name: str = Field(..., description="表名")
    data_list: List[List[str]] = Field(..., description="MySQL数据列表")


@router.post("/html")
async def save_html(params: SaveHTMLParams):
    """保存HTML数据到本地"""
    if SavedData is None:
        raise HTTPException(status_code=500, detail="保存模块未找到")
    
    try:
        saver = SavedData(params.name)
        saver.save_data_html(params.data)
        return {"status": "success", "message": f"HTML已保存为 {params.name}.html"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/csv")
async def save_csv(params: SaveCSVParams):
    """保存CSV数据到本地"""
    if SavedData is None:
        raise HTTPException(status_code=500, detail="保存模块未找到")
    
    try:
        saver = SavedData(params.name)
        columns = params.columns or []
        saver.save_data_csv(params.data_list, *columns)
        return {"status": "success", "message": f"CSV已保存为 {params.name}.csv"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/excel")
async def save_excel(params: SaveExcelParams):
    """保存Excel数据到本地"""
    if SavedData is None:
        raise HTTPException(status_code=500, detail="保存模块未找到")
    
    try:
        saver = SavedData(params.name)
        saver.save_data_excel(params.data_list)
        return {"status": "success", "message": f"Excel已保存为 {params.name}.xlsx"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/mysql")
async def save_mysql(params: SaveMysqlParams):
    """保存数据到MySQL数据库"""
    if SavedData is None:
        raise HTTPException(status_code=500, detail="保存模块未找到")
    
    try:
        saver = SavedData(params.name)
        saver.save_data_mysql(params.data_list)
        return {"status": "success", "message": f"数据已保存到表 {params.name}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class SaveRecordParams(BaseModel):
    url: str = Field(..., description="URL")
    retype: str = Field('text', description="返回类型")
    result: str = Field('', description="响应内容（原始数据）")


@router.post("/record")
async def save_record(params: SaveRecordParams, request: Request):
    """保存爬取记录到数据库（原始数据存文件，预览存数据库）"""
    try:
        import os, uuid
        from utils.data_path import root_path
        from db.session import get_db

        # 确定文件扩展名
        ext = '.html' if params.retype == 'text' else '.json' if params.retype == 'json' else '.bin'
        data = params.result.encode('utf-8') if isinstance(params.result, str) else params.result

        # 先创建记录拿到 ID，用 ID 做文件名
        crawl_dir = os.path.join(root_path(), 'data', 'crawl')
        os.makedirs(crawl_dir, exist_ok=True)

        # 用 UUID 临时文件名，保存后再确定
        file_id = str(uuid.uuid4())[:8]
        file_name = f"{file_id}{ext}"
        file_path = os.path.join(crawl_dir, file_name)

        with open(file_path, 'wb') as f:
            f.write(data)

        preview = data.decode('utf-8', errors='replace')[:2000]
        result_length = len(data)

        db = get_db()
        user_id = getattr(request.state, "user_id", None)
        r = db.save_crawl_record(params.url, params.retype, file_path, preview, result_length, user_id)
        return {"status": "success", "id": r["id"], "duplicate": r.get("duplicate", False), "file_path": file_path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/check")
async def check_record(request: Request, url: str = ""):
    """检查 URL 是否已爬取过"""
    if not url:
        return {"exists": False}
    try:
        from db.session import get_db, CrawlRecord
        db = get_db()
        user_id = getattr(request.state, "user_id", None)
        sess = db.Session()
        try:
            q = sess.query(CrawlRecord).filter_by(url=url)
            if user_id is not None:
                q = q.filter(CrawlRecord.user_id == user_id)
            existing = q.first()
            if existing:
                return {"exists": True, "id": existing.id, "create_time": str(existing.create_time)[:19] if existing.create_time else ""}
            return {"exists": False}
        finally:
            sess.close()
    except Exception as e:
        return {"exists": False, "error": str(e)}


@router.get("/records")
async def get_records(request: Request, page: int = 1, limit: int = 20):
    """获取爬取记录列表"""
    try:
        from db.session import get_db
        db = get_db()
        user_id = getattr(request.state, "user_id", None)
        records, total = db.get_crawl_records(user_id, page, limit)
        return {"records": records, "total": total, "page": page, "limit": limit}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/record/{rid}")
async def get_record(rid: int, request: Request):
    """获取单条爬取记录的完整内容"""
    try:
        from db.session import get_db
        db = get_db()
        record = db.get_crawl_record(rid)
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")
        return record
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/record/{rid}")
async def delete_record(rid: int, request: Request):
    """删除爬取记录"""
    try:
        from db.session import get_db
        db = get_db()
        ok = db.delete_crawl_record(rid)
        if not ok:
            raise HTTPException(status_code=404, detail="记录不存在")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/record/{rid}/file")
async def read_record_file(rid: int, request: Request):
    """读取爬取记录的原始文件内容"""
    try:
        import os
        from db.session import get_db
        db = get_db()
        record = db.get_crawl_record(rid)
        if not record or not record.get("file_path"):
            raise HTTPException(status_code=404, detail="文件不存在")
        path = record["file_path"]
        if not os.path.isfile(path):
            raise HTTPException(status_code=404, detail="文件已丢失")
        ext = os.path.splitext(path)[1].lower()
        if ext == '.html':
            with open(path, 'r', encoding='utf-8') as f:
                return {"type": "html", "content": f.read()}
        elif ext == '.json':
            with open(path, 'r', encoding='utf-8') as f:
                return {"type": "json", "content": f.read()}
        else:
            with open(path, 'rb') as f:
                import base64
                return {"type": "binary", "data": base64.b64encode(f.read()).decode(), "file_path": path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))