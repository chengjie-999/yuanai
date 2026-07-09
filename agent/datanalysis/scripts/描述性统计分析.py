# %% [markdown]
# # 描述性统计分析
# 数据清洗 + 统计量 + 分布图/热力图/箱线图（matplotlib + seaborn + plotly 全栈）。

# %%
import os, sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from utils.data_path import root_path

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

__script_name__ = "描述性统计分析"
__script_desc__ = "对数据集执行描述性统计分析：数据清洗、统计量、分布图、热力图、箱线图。参数: dataset_id(必填, 数据集ID), chart_type(可选, all/static/interactive，默认all)"
__script_tags__ = ["统计分析"]
__script_params__ = ["dataset_id", "chart_type"]

# 用于收集图表路径（脚本末尾输出标记）
_图表列表 = []
_HTML列表 = []

# %% [markdown]
# ### 参数

# %%
数据集ID = int(sys.argv[1]) if len(sys.argv) > 1 else 1
图表类型 = sys.argv[2] if len(sys.argv) > 2 else "all"  # all / static / interactive

出静态图 = 图表类型 in ("all", "static")
出交互图 = 图表类型 in ("all", "interactive")

# %% [markdown]
# ### 加载

# %%
from db.session import get_db
db = get_db()
ds = db.get_dataset(数据集ID)
if not ds:
    raise FileNotFoundError(f"数据集 #{数据集ID} 不存在")

fp, ft = ds["file_path"], ds["file_type"]
if ft == "csv":
    df = pd.read_csv(fp)
elif ft in ("xlsx", "xls"):
    df = pd.read_excel(fp)
elif ft == "json":
    df = pd.read_json(fp)
else:
    raise ValueError(f"不支持的文件类型: {ft}")

total_rows = len(df)
print(f"数据集 #{数据集ID}「{ds['name']}」: {total_rows} 行, {len(df.columns)} 列")

# %% [markdown]
# ### 数据清洗

# %%
cleaning_log = []

before = len(df)
df = df.dropna(how="all").reset_index(drop=True)
if len(df) < before:
    cleaning_log.append(f"去除 {before - len(df)} 行全空数据")

before = len(df)
df = df.drop_duplicates().reset_index(drop=True)
if len(df) < before:
    cleaning_log.append(f"去除 {before - len(df)} 行重复数据")

df.columns = [c.strip() for c in df.columns]

num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
for col in num_cols:
    missing = df[col].isnull().sum()
    if missing > 0:
        median_val = df[col].median()
        df[col] = df[col].fillna(median_val)
        cleaning_log.append(f"列「{col}」缺失 {missing} 个值，已用中位数 {median_val:.2f} 填充")

    Q1, Q3 = df[col].quantile(0.25), df[col].quantile(0.75)
    IQR = Q3 - Q1
    lower, upper = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
    outliers = ((df[col] < lower) | (df[col] > upper)).sum()
    if outliers > 0:
        cleaning_log.append(f"列「{col}」检测到 {outliers} 个异常值 (IQR: [{lower:.2f}, {upper:.2f}])")

cat_cols = df.select_dtypes(include=["object"]).columns.tolist()
for col in cat_cols:
    missing = df[col].isnull().sum()
    if missing > 0:
        df[col] = df[col].fillna("未知")
        cleaning_log.append(f"列「{col}」缺失 {missing} 个值，已用「未知」填充")

if cleaning_log:
    for log in cleaning_log:
        print(f"  {log}")

# %% [markdown]
# ### 统计量

# %%
print(f"\n## {ds['name']}")
print(f"原始行数: {total_rows}  ·  清洗后: {len(df)}  ·  列数: {len(df.columns)}")

if num_cols:
    print("\n### 数值列统计")
    print(df[num_cols].describe().to_string())

if cat_cols:
    print(f"\n### 分类列 ({len(cat_cols)}): {', '.join(cat_cols)}")
    for col in cat_cols[:6]:
        top = df[col].value_counts().head(5)
        print(f"  {col}: {dict(top)}")

# %% [markdown]
# ### numpy 高级统计：偏度/峰度/正态性检验

# %%
from scipy import stats as scipy_stats

正态检验结果 = []
if num_cols:
    print("\n### 分布特征")
    for col in num_cols[:min(len(num_cols), 12)]:
        col_data = df[col].dropna()
        偏度 = float(col_data.skew())
        峰度 = float(col_data.kurtosis())
        # Jarque-Bera 正态性检验
        if len(col_data) >= 8:
            jb_stat, jb_p = scipy_stats.jarque_bera(col_data)
            is_normal = jb_p > 0.05
            正态检验结果.append({
                "列": col, "偏度": round(偏度, 3), "峰度": round(峰度, 3),
                "JB_p值": round(jb_p, 4), "正态": is_normal,
            })
        distribution_desc = "正态分布" if is_normal else "非正态分布"
        print(f"  {col}: 偏度={偏度:.3f}  峰度={峰度:.3f}  {distribution_desc} (JB p={jb_p:.4f})")

# %% [markdown]
# ### 图表输出目录

# %%
out_dir = os.path.join(root_path(), "data", "analysis", str(数据集ID))
os.makedirs(out_dir, exist_ok=True)

# %% [markdown]
# ### seaborn 分布图 — 直方图 + KDE 叠加

# %%
if 出静态图 and num_cols:
    n = min(len(num_cols), 9)
    cols = 3; rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(12, 3 * rows))
    axes = axes.flatten() if n > 1 else [axes]

    for i, col in enumerate(num_cols[:n]):
        col_data = df[col].dropna()
        # 直方图 + KDE 叠加（seaborn）
        sns.histplot(col_data, bins=30, kde=True, color="#42a5f5", edgecolor="#fff",
                     alpha=0.6, line_kws={"linewidth": 1.5, "color": "#1565c0"}, ax=axes[i])
        axes[i].set_title(col, fontsize=10)
        axes[i].tick_params(labelsize=8)

    for j in range(n, len(axes)):
        axes[j].set_visible(False)

    plt.tight_layout()
    fig.savefig(os.path.join(out_dir, "distribution.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)
    _图表列表.append(os.path.join(out_dir, "distribution.png"))
    print("分布图已保存（直方图+KDE）")

# %% [markdown]
# ### seaborn 热力图 — 替代 matplotlib imshow

# %%
if 出静态图 and len(num_cols) >= 2:
    top = num_cols[:12]
    corr = df[top].corr()

    fig, ax = plt.subplots(figsize=(max(8, len(top) * 0.6), max(6, len(top) * 0.5)))
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    sns.heatmap(corr, mask=mask, annot=True, fmt=".2f", cmap="RdBu_r",
                vmin=-1, vmax=1, center=0, square=True,
                linewidths=0.5, linecolor="#eee",
                cbar_kws={"shrink": 0.7},
                xticklabels=[str(c)[:20] for c in top],
                yticklabels=[str(c)[:20] for c in top],
                ax=ax)
    ax.set_title("相关系数热力图", fontsize=11)
    ax.tick_params(labelsize=8)
    plt.tight_layout()
    fig.savefig(os.path.join(out_dir, "heatmap.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)
    _图表列表.append(os.path.join(out_dir, "heatmap.png"))
    print("热力图已保存（seaborn）")

# %% [markdown]
# ### seaborn 箱线图 — 替代 matplotlib boxplot

# %%
if 出静态图 and num_cols:
    top = num_cols[:min(len(num_cols), 10)]
    sample = df[top].dropna()
    if len(sample) > 0:
        df_melt = sample.melt(var_name="列", value_name="值")
        fig, ax = plt.subplots(figsize=(max(8, len(top) * 0.7), 5))
        sns.boxplot(data=df_melt, x="列", y="值", palette="Set2", ax=ax,
                    flierprops=dict(marker="o", markersize=3, alpha=0.4))
        ax.tick_params(axis="x", rotation=45, labelsize=8)
        ax.set_title("箱线图（异常值检测）", fontsize=11)
        plt.tight_layout()
        fig.savefig(os.path.join(out_dir, "boxplot.png"), dpi=120, bbox_inches="tight")
        plt.close(fig)
        _图表列表.append(os.path.join(out_dir, "boxplot.png"))
        print("箱线图已保存（seaborn）")

# %% [markdown]
# ### plotly 交互式分布图

# %%
if 出交互图 and num_cols:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    n_interactive = min(len(num_cols), 9)
    cols_i = 3; rows_i = (n_interactive + cols_i - 1) // cols_i
    fig = make_subplots(rows=rows_i, cols=cols_i,
                        subplot_titles=[str(c)[:30] for c in num_cols[:n_interactive]])

    for i, col in enumerate(num_cols[:n_interactive]):
        row, col_idx = i // cols_i + 1, i % cols_i + 1
        col_data = df[col].dropna()
        fig.add_trace(go.Histogram(x=col_data, name=str(col), marker_color="#589df6",
                                   nbinsx=30, opacity=0.75), row=row, col=col_idx)

    fig.update_layout(height=220 * rows_i, showlegend=False, margin=dict(l=20, r=20, t=40, b=20),
                      template="plotly_white")
    HTML分布路径 = os.path.join(out_dir, "distribution_interactive.html")
    fig.write_html(HTML分布路径, include_plotlyjs="cdn", full_html=True,
                   config={"displayModeBar": True, "responsive": True})
    _HTML列表.append(HTML分布路径)
    print("交互式分布图已保存")

# %% [markdown]
# ### plotly 交互式热力图

# %%
if 出交互图 and len(num_cols) >= 2:
    import plotly.graph_objects as go

    top_i = num_cols[:12]
    corr_i = df[top_i].corr().round(2)
    fig = go.Figure(data=go.Heatmap(
        z=corr_i.values, x=[str(c)[:20] for c in top_i], y=[str(c)[:20] for c in top_i],
        colorscale="RdBu_r", zmin=-1, zmax=1,
        text=corr_i.values, texttemplate="%{text:.2f}",
        hovertemplate="%{x} × %{y}: %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(height=500, margin=dict(l=60, r=20, t=30, b=80),
                      xaxis_tickangle=-45, template="plotly_white")
    HTML热力路径 = os.path.join(out_dir, "heatmap_interactive.html")
    fig.write_html(HTML热力路径, include_plotlyjs="cdn", full_html=True,
                   config={"displayModeBar": True, "responsive": True})
    _HTML列表.append(HTML热力路径)
    print("交互式热力图已保存")

# %% [markdown]
# ### plotly 交互式箱线图

# %%
if 出交互图 and num_cols:
    import plotly.graph_objects as go

    top_box = num_cols[:min(len(num_cols), 10)]
    fig = go.Figure()
    for col in top_box:
        fig.add_trace(go.Box(y=df[col].dropna(), name=str(col)[:20], marker_color="#589df6"))

    fig.update_layout(height=400, showlegend=False, margin=dict(l=20, r=20, t=30, b=80),
                      xaxis_tickangle=-45, template="plotly_white")
    HTML箱线路径 = os.path.join(out_dir, "boxplot_interactive.html")
    fig.write_html(HTML箱线路径, include_plotlyjs="cdn", full_html=True,
                   config={"displayModeBar": True, "responsive": True})
    _HTML列表.append(HTML箱线路径)
    print("交互式箱线图已保存")

# %% [markdown]
# ### 保存清洗后数据

# %%
clean_path = os.path.join(out_dir, "cleaned.csv")
df.to_csv(clean_path, index=False, encoding="utf-8-sig")
print(f"清洗后数据已保存 -> {clean_path}")

# %% [markdown]
# ### 输出标记

# %%
if _图表列表:
    print(f"__IMAGES__:{','.join(_图表列表)}")
if _HTML列表:
    print(f"__HTML__:{','.join(_HTML列表)}")

import json as _json
_result = {
    "name": ds["name"], "id": 数据集ID,
    "rows_original": total_rows, "rows_cleaned": len(df), "columns": len(df.columns),
    "num_cols": len(num_cols), "cat_cols": len(cat_cols),
    "cleaned_path": clean_path,
    "normality_tests": 正态检验结果,
    "cleaning_log": cleaning_log,
}
print(f"__RESULT__:{_json.dumps(_result, ensure_ascii=False)}")
