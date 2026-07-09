# %% [markdown]
# # 相关性分析
# 多方法相关系数矩阵 + 显著性检验 + 热力图/聚类图/散点矩阵。

# %%
import os, sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats as scipy_stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from utils.data_path import root_path

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

__script_name__ = "相关性分析"
__script_desc__ = "对数据集数值列做多方法相关系数分析：Pearson/Spearman/Kendall + 显著性检验 + 热力图/聚类图/散点矩阵。参数: dataset_id(必填), method(pearson/spearman/kendall), top_n(默认15)"
__script_tags__ = ["统计分析"]
__script_params__ = ["dataset_id", "method", "top_n"]

_图表列表 = []
_HTML列表 = []

# %% [markdown]
# ### 参数

# %%
数据集ID = int(sys.argv[1]) if len(sys.argv) > 1 else 1
方法 = sys.argv[2] if len(sys.argv) > 2 else "pearson"
特征数 = int(sys.argv[3]) if len(sys.argv) > 3 else 15

if 方法 not in ("pearson", "spearman", "kendall"):
    raise ValueError(f"不支持的方法: {方法}，可选 pearson/spearman/kendall")

# %% [markdown]
# ### 加载数据

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

print(f"数据集 #{数据集ID}「{ds['name']}」: {len(df)} 行, {len(df.columns)} 列")

# %% [markdown]
# ### 数值特征选择

# %%
数值列 = df.select_dtypes(include=[np.number]).columns.tolist()
数值列 = [c for c in 数值列 if df[c].nunique() > 1]  # 排除常量列
if len(数值列) < 2:
    raise ValueError(f"数值列不足（需要至少 2 列），当前: {数值列}")
if len(数值列) > 特征数:
    数值列 = 数值列[:特征数]

# 清洗：中位数填充缺失值
for col in 数值列:
    if df[col].isnull().any():
        df[col] = df[col].fillna(df[col].median())

print(f"分析列 ({len(数值列)}): {', '.join(数值列)}")

# %% [markdown]
# ### 相关系数矩阵

# %%
相关矩阵 = df[数值列].corr(method=方法 if 方法 in ("pearson", "spearman") else "kendall")
print(f"\n## {方法.upper()} 相关系数矩阵")
print(f"列数: {len(数值列)}")

# 显著性检验 (Pearson only, 其他方法用 scipy 逐个计算)
显著对 = []
if 方法 == "pearson":
    n = len(df)
    for i, c1 in enumerate(数值列):
        for j, c2 in enumerate(数值列):
            if i >= j:
                continue
            r = 相关矩阵.loc[c1, c2]
            if abs(r) < 0.3:
                continue
            # t-test for correlation significance
            t_stat = r * np.sqrt((n - 2) / (1 - r**2))
            p_val = 2 * scipy_stats.t.sf(abs(t_stat), n - 2)
            if p_val < 0.05:
                显著对.append({"特征1": c1, "特征2": c2, "相关系数": round(r, 4), "p值": round(p_val, 4)})
else:
    for i, c1 in enumerate(数值列):
        for j, c2 in enumerate(数值列):
            if i >= j:
                continue
            r = 相关矩阵.loc[c1, c2]
            if abs(r) < 0.3:
                continue
            if 方法 == "spearman":
                r_stat, p_val = scipy_stats.spearmanr(df[c1].dropna(), df[c2].dropna())
            else:
                r_stat, p_val = scipy_stats.kendalltau(df[c1].dropna(), df[c2].dropna())
            if p_val < 0.05:
                显著对.append({"特征1": c1, "特征2": c2, "相关系数": round(r, 4), "p值": round(p_val, 4)})

显著对.sort(key=lambda x: abs(x["相关系数"]), reverse=True)
if 显著对:
    print(f"\n显著相关对 (|r|>0.3, p<0.05, 共{len(显著对)}对):")
    for pair in 显著对[:20]:
        direction = "正" if pair["相关系数"] > 0 else "负"
        print(f"  {pair['特征1']} × {pair['特征2']}: r={pair['相关系数']:.4f} p={pair['p值']:.4f} ({direction}相关)")

# %% [markdown]
# ### 图表目录

# %%
图表目录 = os.path.join(root_path(), "data", "analysis", "correlation", str(数据集ID))
os.makedirs(图表目录, exist_ok=True)

# %% [markdown]
# ### seaborn 热力图

# %%
fig, ax = plt.subplots(figsize=(max(10, len(数值列) * 0.55), max(8, len(数值列) * 0.5)))
mask = np.triu(np.ones_like(相关矩阵, dtype=bool), k=1)
sns.heatmap(相关矩阵, mask=mask, annot=True, fmt=".2f", cmap="RdBu_r",
            vmin=-1, vmax=1, center=0, square=True,
            linewidths=0.5, linecolor="#eee",
            cbar_kws={"shrink": 0.7, "label": 方法.upper()},
            ax=ax)
ax.set_title(f"{方法.upper()} 相关系数热力图", fontsize=13, fontweight="bold")
ax.tick_params(labelsize=8)
plt.tight_layout()
热力图路径 = os.path.join(图表目录, "heatmap.png")
fig.savefig(热力图路径, dpi=150, bbox_inches="tight")
plt.close(fig)
_图表列表.append(热力图路径)
print("热力图已保存")

# %% [markdown]
# ### seaborn 聚类热力图（列 >= 4 时）

# %%
if len(数值列) >= 4:
    fig = sns.clustermap(相关矩阵, annot=True, fmt=".2f", cmap="RdBu_r",
                          vmin=-1, vmax=1, center=0,
                          linewidths=0.5, figsize=(max(10, len(数值列) * 0.6), max(8, len(数值列) * 0.5)))
    聚类图路径 = os.path.join(图表目录, "clustermap.png")
    fig.savefig(聚类图路径, dpi=150, bbox_inches="tight")
    plt.close("all")
    _图表列表.append(聚类图路径)
    print("聚类热力图已保存")

# %% [markdown]
# ### seaborn pairplot（最多 6 列）

# %%
if len(数值列) >= 3:
    样本列 = 数值列[:min(len(数值列), 6)]
    样本数据 = df[样本列].dropna().sample(min(500, len(df)), random_state=42)
    g = sns.pairplot(样本数据, diag_kind="kde",
                     plot_kws={"alpha": 0.4, "s": 15},
                     diag_kws={"fill": True, "alpha": 0.4})
    g.fig.suptitle("特征散点矩阵 (Pairplot)", y=1.01, fontsize=12)
    散点矩阵路径 = os.path.join(图表目录, "pairplot.png")
    g.fig.savefig(散点矩阵路径, dpi=120, bbox_inches="tight")
    plt.close("all")
    _图表列表.append(散点矩阵路径)
    print("散点矩阵已保存")

# %% [markdown]
# ### plotly 交互式热力图

# %%
import plotly.graph_objects as go
import plotly.express as px

fig = go.Figure(data=go.Heatmap(
    z=相关矩阵.values, x=[str(c)[:25] for c in 数值列], y=[str(c)[:25] for c in 数值列],
    colorscale="RdBu_r", zmin=-1, zmax=1,
    text=np.round(相关矩阵.values, 2), texttemplate="%{text:.2f}",
    hovertemplate="%{x} × %{y}: %{z:.2f}<extra></extra>",
))
fig.update_layout(height=max(500, len(数值列) * 25), margin=dict(l=80, r=30, t=50, b=100),
                  xaxis_tickangle=-45,
                  title=f"{方法.upper()} 交互式相关系数热力图")
HTML热力图路径 = os.path.join(图表目录, "heatmap_interactive.html")
fig.write_html(HTML热力图路径, include_plotlyjs="cdn", full_html=True,
               config={"displayModeBar": True, "responsive": True})
_HTML列表.append(HTML热力图路径)
print("交互式热力图已保存")

# %% [markdown]
# ### plotly 交互式散点矩阵（3-8 列时）

# %%
if 3 <= len(数值列) <= 8:
    样本列2 = 数值列[:8]
    样本数据2 = df[样本列2].dropna().sample(min(300, len(df)), random_state=42)
    fig = px.scatter_matrix(样本数据2, dimensions=样本列2,
                            title=f"{方法.upper()} 交互式散点矩阵",
                            opacity=0.5)
    fig.update_traces(diagonal_visible=False, marker=dict(size=4))
    fig.update_layout(height=600)
    HTML散点路径 = os.path.join(图表目录, "scatter_matrix.html")
    fig.write_html(HTML散点路径, include_plotlyjs="cdn", full_html=True,
                   config={"displayModeBar": True, "responsive": True})
    _HTML列表.append(HTML散点路径)
    print("交互式散点矩阵已保存")

# %% [markdown]
# ### 输出标记

# %%
if _图表列表:
    print(f"__IMAGES__:{','.join(_图表列表)}")
if _HTML列表:
    print(f"__HTML__:{','.join(_HTML列表)}")

import json as _json
_result = {
    "method": 方法,
    "features": len(数值列),
    "feature_names": 数值列,
    "significant_pairs": 显著对[:30],
    "corr_matrix": 相关矩阵.round(3).to_dict(),
}
print(f"__RESULT__:{_json.dumps(_result, ensure_ascii=False)}")
