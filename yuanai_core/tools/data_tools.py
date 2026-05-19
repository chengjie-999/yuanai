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
    """
    列出所有可用的数据集。返回 ID、名称、类型、大小、行数、列信息。
    适用场景：用户说"我有哪些数据""看看有什么数据集"时调用。
    """
    from db.session import get_db

    db = get_db()
    datasets = db.get_datasets()
    if not datasets:
        return "暂无数据集。请在「数据工作台」上传 CSV/Excel/JSON 文件。"

    lines = [f"共 {len(datasets)} 个数据集：", ""]
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
    """
    预览数据集的前几行数据。输入 dataset_id（整数）。
    适用场景：用户说"看看这个数据长什么样""预览一下"时调用。
    """
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
    """
    分析指定的数据集。输入 dataset_id（整数，可从 /api/v1/data/datasets 获取列表）。
    返回：基本统计量、相关系数矩阵、缺失值统计，以及分布图/热力图/箱线图。

    适用场景：用户说"分析这个数据""看看有什么规律"时调用。
    """
    import json as _json, os as _os
    from db.session import get_db
    from concurrent.futures import ProcessPoolExecutor

    db = get_db()
    ds = db.get_dataset(dataset_id)
    if not ds:
        return f"数据集 #{dataset_id} 不存在"

    # check Redis cache first
    try:
        from db.redis_client import get_redis
        rds = get_redis()
        path = ds["file_path"]
        file_mtime = _os.path.getmtime(path) if _os.path.exists(path) else 0
        cached_mtime = rds.get(f"analysis_mtime:{dataset_id}")
        if cached_mtime and int(cached_mtime) >= file_mtime:
            cached = rds.get(f"analysis:{dataset_id}")
            if cached:
                result = _json.loads(cached)
                return _format_analysis_result(result)
    except Exception:
        pass

    # run in subprocess to bypass GIL
    from yuanai_core.pure.analysis import run_analysis
    with ProcessPoolExecutor(max_workers=1) as pool:
        result = pool.submit(run_analysis, ds, dataset_id).result(timeout=120)

    # cache to Redis
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
    """Format analysis result as markdown text for AI chat."""
    images = [f"data:image/png;base64,{ch['data']}" for ch in result.get("charts", []) if ch.get("data")]
    lines = [
        f"## 📊 {result['name']}",
        f"行数: {result['row_count']}  ·  列数: {len(result.get('columns', []))}",
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
