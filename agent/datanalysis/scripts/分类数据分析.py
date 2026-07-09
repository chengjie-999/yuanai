# %% [markdown]
# # 分类数据分析
# 频次统计 + 交叉表 + 卡方检验 + 小提琴图/增强箱线图/柱状图/树图/旭日图。

# %%
import os, sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from utils.data_path import root_path

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

__script_name__ = "分类数据分析"
__script_desc__ = "对分类变量做频次分析+交叉表+卡方检验，配合 violin/boxen/bar/point 高级可视化。参数: dataset_id(必填), cat_cols(可选, 逗号分隔分类列，默认自动选object列), target_col(可选, 数值目标列用于分组比较)"
__script_tags__ = ["统计分析"]
__script_params__ = ["dataset_id", "cat_cols", "target_col"]

_图表列表 = []
_HTML列表 = []

# %% [markdown]
# ### 参数

# %%
数据集ID = int(sys.argv[1]) if len(sys.argv) > 1 else 1
指定分类列 = sys.argv[2] if len(sys.argv) > 2 else ""
指定目标列 = sys.argv[3] if len(sys.argv) > 3 else ""

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
# ### 分类列选择

# %%
if 指定分类列:
    分类列列表 = [c.strip() for c in 指定分类列.split(",")]
    missing = [c for c in 分类列列表 if c not in df.columns]
    if missing:
        raise ValueError(f"分类列不存在: {missing}")
else:
    分类列列表 = df.select_dtypes(include=["object", "category"]).columns.tolist()
    # 也包含低基数列
    for col in df.select_dtypes(include=[np.number]).columns:
        if col == 指定目标列:
            continue
        if df[col].nunique() <= 10 and df[col].nunique() > 1:
            if col not in 分类列列表:
                分类列列表.append(col)

if not 分类列列表:
    raise ValueError("无分类列可用。请通过 cat_cols 参数指定。")

# 限制数量
if len(分类列列表) > 8:
    分类列列表 = 分类列列表[:8]

print(f"分类列 ({len(分类列列表)}): {', '.join(分类列列表)}")

# %% [markdown]
# ### 数值目标列

# %%
数值目标列 = None
if 指定目标列 and 指定目标列 in df.columns:
    if df[指定目标列].dtype in [np.float64, np.float32, np.int64, np.int32]:
        数值目标列 = 指定目标列
        print(f"目标列: {数值目标列}")
    else:
        print(f"目标列「{指定目标列}」非数值，将只做频次分析")
else:
    数值列列表 = df.select_dtypes(include=[np.number]).columns.tolist()
    if 数值列列表:
        数值目标列 = 数值列列表[0]
        print(f"自动选择目标列: {数值目标列}")

# %% [markdown]
# ### 频次分析

# %%
频次结果 = {}
for col in 分类列列表:
    freq = df[col].value_counts().head(10)
    频次结果[col] = [{"类别": str(k), "频次": int(v), "占比": f"{v/len(df)*100:.1f}%"} for k, v in freq.items()]
    print(f"\n## {col} (共{df[col].nunique()}类)")
    for item in 频次结果[col][:8]:
        print(f"  {item['类别']}: {item['频次']} ({item['占比']})")

# %% [markdown]
# ### 交叉表 + 卡方检验（分类 × 分类，最多 6 对）

# %%
卡方结果 = []
if len(分类列列表) >= 2:
    from scipy.stats import chi2_contingency

    for i in range(min(len(分类列列表), 6)):
        for j in range(i + 1, min(len(分类列列表), 6)):
            ctab = pd.crosstab(df[分类列列表[i]], df[分类列列表[j]])
            if ctab.shape[0] < 2 or ctab.shape[1] < 2:
                continue
            try:
                chi2, p, dof, expected = chi2_contingency(ctab)
                n = ctab.sum().sum()
                cramers_v = np.sqrt(chi2 / (n * (min(ctab.shape) - 1))) if min(ctab.shape) > 1 else 0
                卡方结果.append({
                    "列1": 分类列列表[i], "列2": 分类列列表[j],
                    "卡方值": round(chi2, 2), "自由度": dof, "p值": round(p, 4),
                    "Cramér_V": round(cramers_v, 4),
                    "显著": p < 0.05,
                })
                sig = "显著 ✅" if p < 0.05 else "不显著"
                print(f"\n{分类列列表[i]} × {分类列列表[j]}: χ²={chi2:.2f}, p={p:.4f} ({sig}), V={cramers_v:.3f}")
            except Exception as e:
                print(f"卡方检验失败 ({分类列列表[i]} × {分类列列表[j]}): {e}")

# %% [markdown]
# ### 图表目录

# %%
图表目录 = os.path.join(root_path(), "data", "analysis", "categorical", str(数据集ID))
os.makedirs(图表目录, exist_ok=True)

# %% [markdown]
# ### seaborn 频次柱状图（每个分类列）

# %%
for col in 分类列列表[:4]:
    top_cats = df[col].value_counts().head(10).reset_index()
    top_cats.columns = [col, "频次"]

    fig, ax = plt.subplots(figsize=(8, 4))
    sns.barplot(data=top_cats, y=col, x="频次", palette="viridis", ax=ax)
    ax.set_title(f"{col} — 频次分布 (Top 10)", fontsize=11)
    ax.set_xlabel("频次")
    plt.tight_layout()
    频次图路径 = os.path.join(图表目录, f"freq_{col}.png")
    fig.savefig(频次图路径, dpi=120, bbox_inches="tight")
    plt.close(fig)
    _图表列表.append(频次图路径)
print("频次柱状图已保存")

# %% [markdown]
# ### seaborn catplot（小提琴 + 箱线图，需要目标列）

# %%
if 数值目标列 and 分类列列表:
    目标分类 = 分类列列表[:min(len(分类列列表), 3)]
    for col in 目标分类:
        top_cats = df[col].value_counts().head(6).index.tolist()
        sub = df[df[col].isin(top_cats)].copy()

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        # 小提琴图
        try:
            sns.violinplot(data=sub, x=col, y=数值目标列, palette="Set2", ax=ax1, inner="quartile")
        except Exception:
            sns.boxplot(data=sub, x=col, y=数值目标列, palette="Set2", ax=ax1)
        ax1.set_title(f"{col} × {数值目标列} — 小提琴图", fontsize=10)
        ax1.tick_params(axis="x", rotation=30, labelsize=8)

        # 增强箱线图 (boxen)
        try:
            sns.boxenplot(data=sub, x=col, y=数值目标列, palette="Set2", ax=ax2)
        except Exception:
            sns.boxplot(data=sub, x=col, y=数值目标列, palette="Set2", ax=ax2)
        ax2.set_title(f"{col} × {数值目标列} — 增强箱线图", fontsize=10)
        ax2.tick_params(axis="x", rotation=30, labelsize=8)

        plt.tight_layout()
        小提琴路径 = os.path.join(图表目录, f"catplot_{col}.png")
        fig.savefig(小提琴路径, dpi=120, bbox_inches="tight")
        plt.close(fig)
        _图表列表.append(小提琴路径)
    print("分类分布图已保存")

# %% [markdown]
# ### plotly 交互式分组柱状图

# %%
import plotly.express as px

for col in 分类列列表[:3]:
    top = df[col].value_counts().head(12).reset_index()
    top.columns = [col, "频次"]
    top["占比"] = (top["频次"] / top["频次"].sum() * 100).round(1)

    fig = px.bar(top.sort_values("频次"), x="频次", y=col, orientation="h",
                 title=f"{col} — 频次分布",
                 text="占比", color="频次", color_continuous_scale="Viridis")
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(height=max(250, len(top) * 28), margin=dict(l=20, r=60, t=50, b=20),
                      template="plotly_white")
    HTML频次路径 = os.path.join(图表目录, f"freq_{col}_interactive.html")
    fig.write_html(HTML频次路径, include_plotlyjs="cdn", full_html=True,
                   config={"displayModeBar": True, "responsive": True})
    _HTML列表.append(HTML频次路径)
print("交互式频次图已保存")

# %% [markdown]
# ### plotly treemap（首列分类 + 目标列）

# %%
if 数值目标列 and 分类列列表:
    first_col = 分类列列表[0]
    top_cats = df[first_col].value_counts().head(15).index.tolist()
    sub = df[df[first_col].isin(top_cats)]

    fig = px.treemap(sub, path=[first_col], values=数值目标列,
                     title=f"{first_col} — Treemap ({数值目标列})",
                     color=数值目标列, color_continuous_scale="Viridis")
    fig.update_layout(height=400, margin=dict(l=20, r=20, t=50, b=20),
                      template="plotly_white")
    HTML树图路径 = os.path.join(图表目录, "treemap.html")
    fig.write_html(HTML树图路径, include_plotlyjs="cdn", full_html=True,
                   config={"displayModeBar": True, "responsive": True})
    _HTML列表.append(HTML树图路径)
    print("交互式 Treemap 已保存")

# %% [markdown]
# ### plotly 分组柱状图（第二列 × 目标列）

# %%
if 数值目标列 and len(分类列列表) >= 2:
    second_col = 分类列列表[1]
    top_cats2 = df[second_col].value_counts().head(8).index.tolist()
    sub2 = df[df[second_col].isin(top_cats2)]

    分组均值 = sub2.groupby(second_col)[数值目标列].mean().reset_index()
    分组均值.columns = [second_col, f"平均{数值目标列}"]

    fig = px.bar(分组均值.sort_values(f"平均{数值目标列}"), x=second_col, y=f"平均{数值目标列}",
                 title=f"{second_col} × 平均{数值目标列}",
                 color=f"平均{数值目标列}", color_continuous_scale="Blues",
                 text=分组均值[f"平均{数值目标列}"].round(1))
    fig.update_traces(texttemplate="%{text}", textposition="outside")
    fig.update_layout(height=350, margin=dict(l=20, r=20, t=50, b=80),
                      xaxis_tickangle=-30, template="plotly_white")
    HTML分组路径 = os.path.join(图表目录, "grouped_bar.html")
    fig.write_html(HTML分组路径, include_plotlyjs="cdn", full_html=True,
                   config={"displayModeBar": True, "responsive": True})
    _HTML列表.append(HTML分组路径)
    print("交互式分组柱状图已保存")

# %% [markdown]
# ### 输出标记

# %%
if _图表列表:
    print(f"__IMAGES__:{','.join(_图表列表)}")
if _HTML列表:
    print(f"__HTML__:{','.join(_HTML列表)}")

import json as _json
_result = {
    "cat_cols": 分类列列表,
    "target_col": 数值目标列,
    "frequencies": 频次结果,
    "chi_square_tests": 卡方结果,
}
print(f"__RESULT__:{_json.dumps(_result, ensure_ascii=False)}")
