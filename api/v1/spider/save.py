from fastapi import APIRouter, HTTPException
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


@router.post("/save/html")
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


@router.post("/save/csv")
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


@router.post("/save/excel")
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


@router.post("/save/mysql")
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