# %% [markdown]
# # 生物信息学 — 基因表达分布分析
# 直方图 + KDE 核密度曲线，含小提琴图/箱线图/火山图/热力图。

# %%
import sys, os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import gaussian_kde

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from utils.data_path import root_path

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

__script_name__ = "基因表达分布分析"
__script_desc__ = "对基因表达数据（log2_FPKM）做直方图+KDE+小提琴图+火山图+表达热力图分析。参数: file_path(可选, CSV文件路径，默认用内置示例数据)"
__script_tags__ = ["生物信息"]
__script_params__ = ["file_path"]

_图表列表 = []
_HTML列表 = []

# %% [markdown]
# ### 参数

# %%
文件路径 = sys.argv[1] if len(sys.argv) > 1 else ""

# %% [markdown]
# ### 加载数据

# %%
if 文件路径 and os.path.exists(文件路径):
    df = pd.read_csv(文件路径)
    print(f"已加载: {文件路径}")
else:
    data = {
        "Gene": ["Gene_1", "Gene_2", "Gene_3", "Gene_4", "Gene_5"],
        "Chromosome": ["Chr7", "Chr20", "Chr15", "Chr11", "Chr8"],
        "FPKM": [14.404353, 1.786426, 2.601230, 7.630435, 19.579397],
        "Count": [50, 57, 42, 61, 51],
        "P_Value": [0.69, 0.690097, 0.930607, 0.497312, 0.230251],
        "DEG": ["Not Significant"] * 5,
        "log2_FPKM": [3.945266, 1.478416, 1.848490, 3.109433, 4.363129],
    }
    df = pd.DataFrame(data)
    print("使用内置示例数据")
    print(df.to_string(index=False))

# %% [markdown]
# ### 数据清洗

# %%
if "log2_FPKM" in df.columns:
    目标列 = "log2_FPKM"
elif "FPKM" in df.columns:
    df["log2_FPKM"] = np.log2(df["FPKM"] + 1)
    目标列 = "log2_FPKM"
else:
    数值列列表 = df.select_dtypes(include=[np.number]).columns.tolist()
    目标列 = 数值列列表[0] if 数值列列表 else None
    if 目标列 is None:
        raise ValueError("无可用的数值列")

df_clean = df.dropna(subset=[目标列])
print(f"目标列: {目标列}  ·  清洗后: {len(df_clean)} 行")
print(df_clean.head())

# %% [markdown]
# ### numpy 统计量

# %%
表达数据 = df_clean[目标列].to_numpy()
print(f"\n## 表达统计")
print(f"基因数: {len(表达数据)}")
print(f"均值: {表达数据.mean():.3f}")
print(f"中位数: {np.median(表达数据):.3f}")
print(f"标准差: {表达数据.std():.3f}")
print(f"偏度: {pd.Series(表达数据).skew():.3f}")
print(f"峰度: {pd.Series(表达数据).kurtosis():.3f}")
print(f"范围: [{表达数据.min():.3f}, {表达数据.max():.3f}]")

# %% [markdown]
# ### 图表目录

# %%
fig_dir = os.path.join(root_path(), "data", "analysis", "bio")
os.makedirs(fig_dir, exist_ok=True)

# %% [markdown]
# ### matplotlib + seaborn 直方图 + KDE

# %%
fig, ax = plt.subplots(figsize=(10, 6))

# seaborn histplot + KDE
sns.histplot(表达数据, bins=min(30, len(表达数据)//3), kde=True, color="#42a5f5",
             edgecolor="#fff", alpha=0.6, line_kws={"linewidth": 2, "color": "#1565c0"}, ax=ax)

# 叠加 mean/median 线
均值线 = 表达数据.mean()
中位数线 = np.median(表达数据)
ax.axvline(均值线, color="#e53935", linestyle="--", linewidth=1.5, label=f"均值={均值线:.2f}")
ax.axvline(中位数线, color="#66bb6a", linestyle=":", linewidth=1.5, label=f"中位数={中位数线:.2f}")

ax.set_title(f"{目标列} 分布直方图 (n={len(表达数据)})", fontsize=12, fontweight="bold")
ax.set_xlabel(目标列)
ax.set_ylabel("频数")
ax.legend(fontsize=9)

plt.tight_layout()
hist_png = os.path.join(fig_dir, "distribution.png")
fig.savefig(hist_png, dpi=150, bbox_inches="tight")
plt.close(fig)
_图表列表.append(hist_png)
print("分布图已保存")

# %% [markdown]
# ### seaborn 小提琴图 + 箱线图 — 按染色体分组

# %%
if "Chromosome" in df_clean.columns and df_clean["Chromosome"].nunique() >= 2:
    染色体数据 = df_clean.dropna(subset=["Chromosome"])
    if len(染色体数据) >= 4:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        # 小提琴图
        sns.violinplot(data=染色体数据, x="Chromosome", y=目标列, palette="Set2",
                       inner="quartile", ax=ax1)
        ax1.set_title("表达值按染色体分布 — 小提琴图", fontsize=10)
        ax1.tick_params(axis="x", rotation=30, labelsize=8)

        # 箱线图
        sns.boxplot(data=染色体数据, x="Chromosome", y=目标列, palette="Set2", ax=ax2)
        ax2.set_title("表达值按染色体分布 — 箱线图", fontsize=10)
        ax2.tick_params(axis="x", rotation=30, labelsize=8)

        plt.tight_layout()
        chrom_png = os.path.join(fig_dir, "chromosome_comparison.png")
        fig.savefig(chrom_png, dpi=150, bbox_inches="tight")
        plt.close(fig)
        _图表列表.append(chrom_png)
        print("染色体比较图已保存")

# %% [markdown]
# ### seaborn 小提琴图 — 按 DEG 分组

# %%
if "DEG" in df_clean.columns and df_clean["DEG"].nunique() >= 2:
    deg数据 = df_clean.dropna(subset=["DEG"])
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.violinplot(data=deg数据, x="DEG", y=目标列, palette="Set2", inner="quartile", ax=ax)
    ax.set_title("表达值按 DEG 分组 — 小提琴图", fontsize=10)
    plt.tight_layout()
    deg_png = os.path.join(fig_dir, "deg_violin.png")
    fig.savefig(deg_png, dpi=120, bbox_inches="tight")
    plt.close(fig)
    _图表列表.append(deg_png)
    print("DEG 小提琴图已保存")

# %% [markdown]
# ### plotly 交互式直方图 + KDE

# %%
import plotly.figure_factory as ff

fig = ff.create_distplot([表达数据], [目标列], bin_size=(表达数据.max() - 表达数据.min()) / 30,
                          colors=["#589df6"], show_hist=True, show_rug=False)
fig.add_vline(x=均值线, line_dash="dash", line_color="#e53935", annotation_text=f"均值={均值线:.2f}")
fig.add_vline(x=中位数线, line_dash="dot", line_color="#66bb6a", annotation_text=f"中位数={中位数线:.2f}")
fig.update_layout(height=400, margin=dict(l=50, r=20, t=30, b=50),
                  title=f"{目标列} 交互式分布图",
                  xaxis_title=目标列, yaxis_title="密度/频数",
                  template="plotly_white")
html_dist_path = os.path.join(fig_dir, "distribution_interactive.html")
fig.write_html(html_dist_path, include_plotlyjs="cdn", full_html=True,
               config={"displayModeBar": True, "responsive": True})
_HTML列表.append(html_dist_path)
print("交互式分布图已保存")

# %% [markdown]
# ### plotly 火山图（需要 P_Value 和表达数据）

# %%
if "P_Value" in df_clean.columns and 目标列 in df_clean.columns:
    volcano_data = df_clean.dropna(subset=["P_Value", 目标列]).copy()
    volcano_data["-log10(P)"] = -np.log10(volcano_data["P_Value"].clip(lower=1e-300))

    # 差异倍数使用当前值（如果有 control vs treatment 数据可用 log2FC）
    volcano_data["log2FC"] = volcano_data[目标列] - volcano_data[目标列].mean()

    # 显著标记
    volcano_data["显著"] = "Not Significant"
    volcano_data.loc[(volcano_data["-log10(P)"] > 1.3) & (volcano_data["log2FC"] > 1), "显著"] = "Up"
    volcano_data.loc[(volcano_data["-log10(P)"] > 1.3) & (volcano_data["log2FC"] < -1), "显著"] = "Down"

    import plotly.express as px

    fig = px.scatter(volcano_data, x="log2FC", y="-log10(P)", color="显著",
                     color_discrete_map={"Not Significant": "#999", "Up": "#e53935", "Down": "#43a047"},
                     hover_data=["Gene"] if "Gene" in volcano_data.columns else None,
                     title="火山图 (Volcano Plot)")
    fig.add_hline(y=1.3, line_dash="dash", line_color="#999", annotation_text="p=0.05")
    fig.add_vline(x=1, line_dash="dash", line_color="#e53935", annotation_text="FC=2")
    fig.add_vline(x=-1, line_dash="dash", line_color="#43a047", annotation_text="FC=0.5")
    fig.update_layout(height=450, margin=dict(l=50, r=20, t=40, b=50),
                      template="plotly_white")
    html_volcano_path = os.path.join(fig_dir, "volcano.html")
    fig.write_html(html_volcano_path, include_plotlyjs="cdn", full_html=True,
                   config={"displayModeBar": True, "responsive": True})
    _HTML列表.append(html_volcano_path)
    print("交互式火山图已保存")

# %% [markdown]
# ### plotly 基因表达热力图（多基因时）

# %%
if "Gene" in df_clean.columns and len(特征数据 := df_clean.dropna(subset=["Gene", 目标列])) >= 3:
    基因数 = min(len(特征数据), 20)
    热力数据 = 特征数据.head(基因数)[["Gene", 目标列]].set_index("Gene")

    import plotly.graph_objects as go

    fig = go.Figure(data=go.Heatmap(
        z=热力数据.values, x=[目标列], y=热力数据.index.tolist(),
        colorscale="RdYlBu_r",
        text=np.round(热力数据.values, 2), texttemplate="%{text:.2f}",
        hovertemplate="Gene: %{y}<br>%{x}: %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(height=max(300, 基因数 * 18), margin=dict(l=100, r=20, t=30, b=50),
                      template="plotly_white", title="基因表达热力图")
    html_heat_path = os.path.join(fig_dir, "expression_heatmap.html")
    fig.write_html(html_heat_path, include_plotlyjs="cdn", full_html=True,
                   config={"displayModeBar": True, "responsive": True})
    _HTML列表.append(html_heat_path)
    print("交互式表达热力图已保存")

# %% [markdown]
# ### 输出标记

# %%
if _图表列表:
    print(f"__IMAGES__:{','.join(_图表列表)}")
if _HTML列表:
    print(f"__HTML__:{','.join(_HTML列表)}")

import json as _json
_result = {
    "gene_count": int(len(表达数据)),
    "target_col": 目标列,
    "mean": round(float(表达数据.mean()), 3),
    "median": round(float(np.median(表达数据)), 3),
    "std": round(float(表达数据.std()), 3),
    "skewness": round(float(pd.Series(表达数据).skew()), 3),
    "kurtosis": round(float(pd.Series(表达数据).kurtosis()), 3),
}
print(f"__RESULT__:{_json.dumps(_result, ensure_ascii=False)}")
