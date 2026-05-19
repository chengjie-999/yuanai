"""数据分析核心逻辑 — 纯函数，无框架依赖。"""
import os
import base64
from utils.data_path import root_path

ANALYSIS_DIR = os.path.join(root_path(), "data", "analysis")


def run_analysis(ds: dict, ds_id: int, charts: bool = True) -> dict:
    """同步分析数据集。charts=False 时只做 pandas 统计，跳过 matplotlib。"""
    import pandas as pd

    path = ds["file_path"]
    ft = ds["file_type"]
    if ft == "csv":
        df = pd.read_csv(path)
    elif ft in ("xlsx", "xls"):
        df = pd.read_excel(path)
    elif ft == "json":
        df = pd.read_json(path)
    else:
        raise ValueError(f"unsupported type: {ft}")

    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    desc = df[num_cols].describe().round(2).to_dict() if num_cols else {}
    missing = {k: int(v) for k, v in df.isnull().sum().to_dict().items() if v > 0}
    corr_data = df[num_cols].corr().round(2).values.tolist() if len(num_cols) >= 2 else []
    col_info = [{"name": str(c), "dtype": str(df[c].dtype)} for c in df.columns]

    chart_data = []
    if charts:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "WenQuanYi Micro Hei", "sans-serif"]
        plt.rcParams["axes.unicode_minus"] = False
        chart_dir = os.path.join(ANALYSIS_DIR, str(ds_id))
        os.makedirs(chart_dir, exist_ok=True)

        def _save(fig, name: str):
            fig.savefig(os.path.join(chart_dir, f"{name}.png"), format="png", dpi=100, bbox_inches="tight")

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
                _save(fig, "distribution")
                plt.close(fig)
            except Exception:
                pass

        if len(num_cols) >= 2:
            try:
                fig, ax = plt.subplots(figsize=(8, 6))
                corr = df[num_cols].corr()
                im = ax.imshow(corr, cmap="RdYlBu_r", vmin=-1, vmax=1)
                ax.set_xticks(range(len(num_cols)))
                ax.set_yticks(range(len(num_cols)))
                ax.set_xticklabels(num_cols, rotation=45, ha="right", fontsize=8)
                ax.set_yticklabels(num_cols, fontsize=8)
                fig.colorbar(im, ax=ax, shrink=0.8)
                ax.set_title("Correlation Heatmap", fontsize=10)
                plt.tight_layout()
                _save(fig, "heatmap")
                plt.close(fig)
            except Exception:
                pass

        if num_cols:
            try:
                sample = df[num_cols[:min(len(num_cols), 10)]].dropna()
                if len(sample) > 0:
                    fig, ax = plt.subplots(figsize=(10, 4))
                    sample.boxplot(ax=ax, rot=45)
                    ax.set_title("Boxplot", fontsize=10)
                    ax.tick_params(labelsize=8)
                    plt.tight_layout()
                    _save(fig, "boxplot")
                    plt.close(fig)
            except Exception:
                pass

        for name in ("distribution", "heatmap", "boxplot"):
            fpath = os.path.join(chart_dir, f"{name}.png")
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                chart_data.append({"name": name, "url": f"/api/v1/data/analysis-image/{ds_id}/{name}", "data": b64})

    return {
        "id": ds_id, "name": ds["name"], "row_count": len(df),
        "columns": col_info, "num_cols": num_cols,
        "describe": desc, "missing": missing,
        "corr_labels": num_cols,
        "corr": corr_data,
        "charts": chart_data,
    }
