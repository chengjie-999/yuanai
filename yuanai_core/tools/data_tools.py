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
    from db.session import get_db

    db = get_db()
    ds = db.get_dataset(dataset_id)
    if not ds:
        return f"数据集 #{dataset_id} 不存在"

    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    try:
        path = ds["file_path"]
        ft = ds["file_type"]
        if ft == "csv":
            df = pd.read_csv(path)
        elif ft in ("xlsx", "xls"):
            df = pd.read_excel(path)
        elif ft == "json":
            df = pd.read_json(path)
        else:
            return f"不支持的文件类型: {ft}"
    except Exception as e:
        return f"读取数据集失败: {e}"

    row_count = len(df)
    col_count = len(df.columns)
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    images = []

    # 1. 基本统计
    lines = [
        f"## 📊 {ds['name']}",
        f"行数: {row_count}  ·  列数: {col_count}",
        f"数值列 ({len(num_cols)}): {', '.join(num_cols[:20])}",
        f"分类列 ({len(cat_cols)}): {', '.join(cat_cols[:20])}",
    ]

    if num_cols:
        desc = df[num_cols].describe().round(2)
        lines.append("\n### 数值列统计")
        lines.append("```")
        lines.append(desc.to_string())
        lines.append("```")

    # 2. 缺失值
    missing = df.isnull().sum()
    missing = missing[missing > 0]
    if len(missing) > 0:
        lines.append("\n### 缺失值")
        for col, cnt in missing.items():
            pct = round(cnt / row_count * 100, 1)
            lines.append(f"  {col}: {cnt} ({pct}%)")
    else:
        lines.append("\n### 缺失值: 无")

    # 3. 相关性
    if len(num_cols) >= 2:
        corr = df[num_cols].corr().round(2)
        lines.append("\n### 相关系数矩阵")
        lines.append("```")
        lines.append(corr.to_string())
        lines.append("```")

    # 4. 分布直方图
    if num_cols:
        try:
            n = min(len(num_cols), 9)
            fig, axes = plt.subplots((n + 2) // 3, 3, figsize=(12, 3 * ((n + 2) // 3)))
            axes = axes.flatten() if n > 1 else [axes]
            for i, col in enumerate(num_cols[:n]):
                ax = axes[i]
                df[col].dropna().hist(bins=30, ax=ax, color="#42a5f5", edgecolor="#fff", alpha=0.8)
                ax.set_title(col, fontsize=9)
                ax.tick_params(labelsize=7)
            for i in range(n, len(axes)):
                axes[i].set_visible(False)
            plt.tight_layout()
            images.append(_fig_to_base64(fig))
            plt.close(fig)
        except Exception:
            pass

    # 5. 相关性热力图
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
            images.append(_fig_to_base64(fig))
            plt.close(fig)
        except Exception:
            pass

    # 6. 箱线图
    if len(num_cols) >= 1:
        try:
            sample = df[num_cols[:min(len(num_cols), 10)]].dropna()
            if len(sample) > 0:
                fig, ax = plt.subplots(figsize=(10, 4))
                sample.boxplot(ax=ax, rot=45)
                ax.set_title("Boxplot (outlier detection)", fontsize=10)
                ax.tick_params(labelsize=8)
                plt.tight_layout()
                images.append(_fig_to_base64(fig))
                plt.close(fig)
        except Exception:
            pass

    if images:
        lines.append("\n---")
        lines.append("".join(f"\n![]({img})" for img in images))

    return "\n".join(lines)
