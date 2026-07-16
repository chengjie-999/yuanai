TOOL_CATEGORY = "data"

import io
import base64
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    buf.close()
    return f"data:image/png;base64,{b64}"


@tool
def list_datasets() -> str:
    """List all available datasets with ID, name, size, columns."""
    from db.session import get_db
    db = get_db()
    datasets = db.get_datasets()
    if not datasets:
        return "暂无数据集。请在数据工作台上传 CSV/Excel/JSON 文件。"
    lines = [f"共 {len(datasets)} 个数据集:", ""]
    for ds in datasets:
        cols = ", ".join(c["name"] for c in ds.get("columns", [])[:8])
        more = "..." if len(ds.get("columns", [])) > 8 else ""
        lines.append(
            f"  #{ds['id']} {ds['name']} | {ds['file_type']} | "
            f"{ds['row_count']}行 | {ds['file_size']//1024}KB"
        )
        if cols:
            lines.append(f"     列: {cols}{more}")
    return "\n".join(lines)


@tool
def preview_dataset(dataset_id: int) -> str:
    """Preview first rows of a dataset. dataset_id: integer dataset ID."""
    from db.session import get_db
    db = get_db()
    ds = db.get_dataset(dataset_id)
    if not ds:
        return f"数据集 #{dataset_id} 不存在"
    lines = [
        f"## {ds['name']}",
        f"类型: {ds['file_type']} | 行数: {ds['row_count']} | 列数: {len(ds.get('columns', []))}",
        "",
    ]
    if ds.get("columns"):
        lines.append("| " + " | ".join(c["name"] for c in ds["columns"]) + " |")
        lines.append("|" + "|".join("---" for _ in ds["columns"]) + "|")
        for row in ds.get("preview_rows", [])[:10]:
            vals = [str(row.get(c["name"], ""))[:40] for c in ds["columns"]]
            lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


@tool
def analyze_dataset(dataset_id: int) -> str:
    """Full statistical analysis of a dataset. dataset_id: integer."""
    import json as _json, os as _os
    from db.session import get_db
    from concurrent.futures import ProcessPoolExecutor
    db = get_db()
    ds = db.get_dataset(dataset_id)
    if not ds:
        return f"数据集 #{dataset_id} 不存在"
    # check cache
    try:
        from db.redis_client import get_redis
        rds = get_redis()
        path = ds["file_path"]
        file_mtime = _os.path.getmtime(path) if _os.path.exists(path) else 0
        cached_mtime = rds.get(f"analysis_mtime:{dataset_id}")
        if cached_mtime and int(cached_mtime) >= file_mtime:
            cached = rds.get(f"analysis:{dataset_id}")
            if cached:
                return _format_analysis_result(_json.loads(cached))
    except Exception:
        pass
    from yuanai_core.pure.analysis import run_analysis
    with ProcessPoolExecutor(max_workers=1) as pool:
        result = pool.submit(run_analysis, ds, dataset_id).result(timeout=120)
    try:
        from db.redis_client import get_redis
        rds = get_redis()
        rds.setex(f"analysis:{dataset_id}", 86400, _json.dumps(result, ensure_ascii=False))
        rds.setex(f"analysis_mtime:{dataset_id}", 86400, str(int(
            _os.path.getmtime(ds["file_path"]) if _os.path.exists(ds["file_path"]) else 0
        )))
    except Exception:
        pass
    return _format_analysis_result(result)


def _format_analysis_result(result: dict) -> str:
    images = [f"data:image/png;base64,{ch['data']}" for ch in result.get("charts", []) if ch.get("data")]
    lines = [
        f"## {result['name']}",
        f"行数: {result['row_count']}  列数: {len(result.get('columns', []))}",
        f"数值列 ({len(result.get('num_cols', []))}): {', '.join(result.get('num_cols', [])[:20])}",
    ]
    if result.get("describe"):
        lines.append("\n### 数值列统计")
        lines.append("```")
        import pandas as pd
        desc_df = pd.DataFrame(result["describe"])
        lines.append(desc_df.to_string())
        lines.append("```")
    if result.get("missing"):
        lines.append("\n### 缺失值")
        for col, cnt in result["missing"].items():
            lines.append(f"  {col}: {cnt}")
    else:
        lines.append("\n### 缺失值: 无")
    if result.get("corr") and len(result["corr"]) > 0:
        lines.append("\n### 相关系数矩阵")
        lines.append("```")
        import pandas as pd
        corr_df = pd.DataFrame(result["corr"], columns=result.get("corr_labels", []), index=result.get("corr_labels", []))
        lines.append(corr_df.to_string())
        lines.append("```")
    if images:
        lines.append("\n---")
        lines.append("".join(f"\n![]({img})" for img in images))
    return "\n".join(lines)


@tool
def transform_dataset(dataset_id: int, operation: str, params: str) -> str:
    """Transform dataset. dataset_id: int, operation: filter/groupby_agg/pivot_table,
    params: JSON string e.g. '{"column":"年龄","op":">","value":"30"}' for filter,
    '{"group_col":"城市","agg_col":"销售额","func":"sum"}' for groupby_agg,
    '{"index_col":"日期","columns_col":"类别","values_col":"销售额","aggfunc":"sum"}' for pivot_table."""
    import pandas as pd
    import os, json as _json

    from db.session import get_db
    db = get_db()
    ds = db.get_dataset(dataset_id)
    if not ds:
        return f"数据集 #{dataset_id} 不存在"

    ft = ds["file_type"]
    path = ds["file_path"]
    try:
        if ft == "csv":
            df = pd.read_csv(path)
        elif ft in ("xlsx", "xls"):
            df = pd.read_excel(path)
        elif ft == "json":
            df = pd.read_json(path)
        else:
            return f"不支持的文件类型: {ft}"
    except Exception as e:
        return f"读取文件失败: {e}"

    cfg = _json.loads(params) if isinstance(params, str) else params

    try:
        op = operation.lower()
        if op == "filter":
            col, o, val = cfg["column"], cfg["op"], cfg["value"]
            if o == ">":   df = df[df[col].astype(float) > float(val)]
            elif o == "<": df = df[df[col].astype(float) < float(val)]
            elif o == "==": df = df[df[col].astype(str) == str(val)]
            elif o == "contains": df = df[df[col].astype(str).str.contains(str(val), na=False)]
            else: return f"不支持的操作符: {o}, 可选 > < == contains"
        elif op == "groupby_agg":
            gcol, acol, func = cfg["group_col"], cfg["agg_col"], cfg["func"]
            if func == "count":
                df = df.groupby(gcol).size().reset_index(name="count")
            else:
                df = df.groupby(gcol)[acol].agg(func).reset_index()
        elif op == "pivot_table":
            df = pd.pivot_table(df, index=cfg["index_col"], columns=cfg.get("columns_col"),
                              values=cfg["values_col"], aggfunc=cfg.get("aggfunc", "sum")).reset_index()
        else:
            return f"不支持的操作: {op}, 可选 filter/groupby_agg/pivot_table"
    except Exception as e:
        return f"转换失败: {e}"

    if len(df) == 0:
        return "转换后数据为空"

    os.makedirs(os.environ.get("DATASETS_DIR", "data/datasets"), exist_ok=True)
    base_dir = os.environ.get("DATASETS_DIR", "data/datasets")
    fname = f"{ds['name'].rsplit('.',1)[0]}_{op}_{datetime.now().strftime('%H%M%S')}.csv"
    fpath = os.path.join(base_dir, fname)
    df.to_csv(fpath, index=False, encoding="utf-8-sig")
    new_id = db.add_dataset(
        name=fname, file_path=fpath, file_type="csv",
        file_size=os.path.getsize(fpath), row_count=len(df),
        columns_info=_json.dumps([{"name": str(c), "dtype": str(df[c].dtype)} for c in df.columns], ensure_ascii=False),
        preview_rows=_json.dumps(df.head(10).fillna("").to_dict(orient="records"), ensure_ascii=False),
        user_id=None,
    )
    preview = df.head(5).to_string(index=False)
    return f"转换完成! 新数据集 #{new_id} '{fname}'\n{len(df)}行\n\n前5行:\n```\n{preview}\n```"


@tool
def describe_column(dataset_id: int, column: str) -> str:
    """Stats for one column. dataset_id: int, column: column name. Returns count/mean/std/min/max/quartiles/null/outliers."""
    import pandas as pd, os, json as _json
    from db.session import get_db
    db = get_db()
    ds = db.get_dataset(dataset_id)
    if not ds:
        return f"数据集 #{dataset_id} 不存在"
    try:
        ft, path = ds["file_type"], ds["file_path"]
        df = pd.read_csv(path) if ft == "csv" else (pd.read_excel(path) if ft in ("xlsx","xls") else pd.read_json(path))
    except Exception as e:
        return f"读取失败: {e}"
    if column not in df.columns:
        similar = [c for c in df.columns if column.lower() in c.lower()]
        hint = f"\n相似: {', '.join(similar)}" if similar else ""
        return f"列 '{column}' 不存在, 可用: {', '.join(df.columns[:20])}{hint}"

    col = df[column]
    lines = [f"## {column}", f"类型: {col.dtype}", f"总行数: {len(col)}"]
    if pd.api.types.is_numeric_dtype(col):
        desc = col.describe()
        q1, q3 = desc.get('25%', 0), desc.get('75%', 0)
        iqr = q3 - q1
        lines.append("\n### 数值统计")
        lines.append(f"  计数: {int(desc.get('count',0))}  均值: {desc.get('mean',0):.4f}  标准差: {desc.get('std',0):.4f}")
        lines.append(f"  最小: {desc.get('min',0):.4f}  25%: {q1:.4f}  中位: {desc.get('50%',0):.4f}  75%: {q3:.4f}  最大: {desc.get('max',0):.4f}")
        if iqr > 0:
            lower, upper = q1 - 1.5*iqr, q3 + 1.5*iqr
            outliers = col[(col < lower) | (col > upper)]
            lines.append(f"\n### 异常值 (IQR: {lower:.2f}-{upper:.2f})")
            lines.append(f"  异常值: {len(outliers)}个 ({len(outliers)/len(col)*100:.1f}%)")
            if 0 < len(outliers) <= 10:
                lines.append(f"  值: {outliers.tolist()}")
    else:
        lines.append(f"\n唯一值: {col.nunique()}  空值: {col.isna().sum()}({col.isna().sum()/len(col)*100:.1f}%)")
        top = col.value_counts().head(10)
        lines.append("\n频次 Top 10:")
        for val, cnt in top.items():
            lines.append(f"  {str(val)[:40]}: {cnt}")
    lines.append(f"\n空值: {col.isna().sum()}({col.isna().sum()/len(col)*100:.1f}%)")
    return "\n".join(lines)


@tool
def correlate_columns(dataset_id: int, col1: str, col2: str) -> str:
    """Correlation between two columns. dataset_id: int, col1/col2: column names. Returns Pearson/Spearman/Kendall."""
    import pandas as pd, os
    from db.session import get_db
    db = get_db()
    ds = db.get_dataset(dataset_id)
    if not ds:
        return f"数据集 #{dataset_id} 不存在"
    try:
        ft, path = ds["file_type"], ds["file_path"]
        df = pd.read_csv(path) if ft == "csv" else (pd.read_excel(path) if ft in ("xlsx","xls") else pd.read_json(path))
    except Exception as e:
        return f"读取失败: {e}"
    for cn in [col1, col2]:
        if cn not in df.columns:
            similar = [c for c in df.columns if cn.lower() in c.lower()]
            hint = f" 相似: {', '.join(similar)}" if similar else ""
            return f"列 '{cn}' 不存在{hint}"
    c1, c2 = pd.to_numeric(df[col1], errors='coerce'), pd.to_numeric(df[col2], errors='coerce')
    mask = c1.notna() & c2.notna()
    if mask.sum() < 3:
        return f"有效数值对太少 ({int(mask.sum())}对)"
    def _s(r):
        a = abs(r)
        return "极强" if a>=0.8 else ("强" if a>=0.6 else ("中等" if a>=0.4 else ("弱" if a>=0.2 else "极弱")))
    return (
        f"## {col1} vs {col2} (有效 {int(mask.sum())}对)\n\n"
        f"|方法|系数|强度|\n|---|---|---|\n"
        f"|Pearson|{c1.corr(c2,'pearson'):.4f}|{_s(c1.corr(c2,'pearson'))}|\n"
        f"|Spearman|{c1.corr(c2,'spearman'):.4f}|{_s(c1.corr(c2,'spearman'))}|\n"
        f"|Kendall|{c1.corr(c2,'kendall'):.4f}|{_s(c1.corr(c2,'kendall'))}|\n"
        f"\n*Pearson=线性相关, Spearman/Kendall=单调关系(更稳健)*"
    )


from datetime import datetime
