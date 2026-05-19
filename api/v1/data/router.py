import os
import json
import logging
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from db.session import get_db
from utils.data_path import root_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data", tags=["data"])

DATASETS_DIR = os.path.join(root_path(), "data", "datasets")
os.makedirs(DATASETS_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json"}


def _get_user_id(request: Request) -> int:
    return getattr(request.state, "user_id", None)


def _is_admin(request: Request) -> bool:
    return getattr(request.state, "role", "") == "admin"


@router.post("/upload")
async def upload_dataset(request: Request, file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"unsupported format: {ext}")

    user_id = _get_user_id(request)
    db = get_db()
    ds_id = db.add_dataset(
        name=file.filename, file_path="", file_type=ext.lstrip("."),
        file_size=0, row_count=0, columns_info=[], preview_rows=[],
        user_id=user_id,
    )

    fname = f"{ds_id}_{file.filename}"
    fpath = os.path.join(DATASETS_DIR, fname)
    content = await file.read()
    with open(fpath, "wb") as f:
        f.write(content)

    file_size = len(content)
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
    if not ds:
        raise HTTPException(status_code=404, detail="not found")
    return ds


@router.get("/analyze/{ds_id}")
async def analyze_dataset_api(ds_id: int, request: Request):
    db = get_db()
    ds = db.get_dataset(ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="not found")

    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path = ds["file_path"]
    ft = ds["file_type"]
    try:
        if ft == "csv":
            df = pd.read_csv(path)
        elif ft in ("xlsx", "xls"):
            df = pd.read_excel(path)
        elif ft == "json":
            df = pd.read_json(path)
        else:
            raise HTTPException(status_code=400, detail=f"unsupported type: {ft}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    charts = []

    def _fig_to_b64(fig):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode()
        buf.close()
        return b64

    # histogram
    if num_cols:
        try:
            n = min(len(num_cols), 9)
            fig, axes = plt.subplots((n + 2) // 3, 3, figsize=(12, 3 * ((n + 2) // 3)))
            axes = axes.flatten() if n > 1 else [axes]
            for i, col in enumerate(num_cols[:n]):
                df[col].dropna().hist(bins=30, ax=axes[i], color="#42a5f5", edgecolor="#fff", alpha=0.8)
                axes[i].set_title(col, fontsize=9)
                axes[i].tick_params(labelsize=7)
            for i in range(n, len(axes)):
                axes[i].set_visible(False)
            plt.tight_layout()
            charts.append({"name": "distribution", "data": _fig_to_b64(fig)})
            plt.close(fig)
        except Exception:
            pass

    # heatmap
    if len(num_cols) >= 2:
        try:
            fig, ax = plt.subplots(figsize=(8, 6))
            corr = df[num_cols].corr()
            im = ax.imshow(corr, cmap="RdYlBu_r", vmin=-1, vmax=1)
            ax.set_xticks(range(len(num_cols)))
            ax.set_yticks(range(len(num_cols)))
            ax.set_xticklabels(num_cols, rotation=45, ha="right", fontsize=8)
            ax.set_yticklabels(num_cols, fontsize=8)
            plt.colorbar(im, ax=ax, shrink=0.8)
            ax.set_title("Correlation Heatmap", fontsize=10)
            plt.tight_layout()
            charts.append({"name": "heatmap", "data": _fig_to_b64(fig)})
            plt.close(fig)
        except Exception:
            pass

    # boxplot
    if num_cols:
        try:
            sample = df[num_cols[:min(len(num_cols), 10)]].dropna()
            if len(sample) > 0:
                fig, ax = plt.subplots(figsize=(10, 4))
                sample.boxplot(ax=ax, rot=45)
                ax.set_title("Boxplot", fontsize=10)
                ax.tick_params(labelsize=8)
                plt.tight_layout()
                charts.append({"name": "boxplot", "data": _fig_to_b64(fig)})
                plt.close(fig)
        except Exception:
            pass

    import io, base64 as _b64
    desc = df[num_cols].describe().round(2).to_dict() if num_cols else {}
    missing = {k: int(v) for k, v in df.isnull().sum().to_dict().items() if v > 0}
    corr_data = df[num_cols].corr().round(2).values.tolist() if len(num_cols) >= 2 else []
    col_info = [{"name": str(c), "dtype": str(df[c].dtype)} for c in df.columns]

    return {
        "id": ds_id, "name": ds["name"], "row_count": len(df),
        "columns": col_info, "num_cols": num_cols,
        "describe": desc, "missing": missing,
        "corr_labels": num_cols,
        "corr": corr_data,
        "charts": charts,
    }


@router.delete("/dataset/{ds_id}")
async def delete_dataset(ds_id: int, request: Request):
    db = get_db()
    user_id = None if _is_admin(request) else _get_user_id(request)
    ok = db.delete_dataset(ds_id, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="not found or permission denied")
    return {"ok": True}
