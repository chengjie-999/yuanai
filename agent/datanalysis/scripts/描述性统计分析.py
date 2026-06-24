# %% [markdown]
# # 描述性统计分析
# 数据清洗 + 统计量 + 分布图/热力图/箱线图。

# %%
import os, sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from utils.data_path import root_path

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

__script_name__ = "描述性统计分析"
__script_desc__ = "对数据集执行描述性统计分析：数据清洗、统计量、分布图、箱线图。参数: dataset_id(必填, 数据集ID)"
__script_tags__ = ["统计分析"]
__script_params__ = ["dataset_id"]

# 用于收集图表路径（脚本末尾输出 __IMAGES__ 标记）
_图表列表 = []

# %% [markdown]
# ### 参数

# %%
数据集ID = int(sys.argv[1]) if len(sys.argv) > 1 else 1

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
# ### 分布图

# %%
out_dir = os.path.join(root_path(), "data", "analysis", str(数据集ID))
os.makedirs(out_dir, exist_ok=True)

if num_cols:
    n = min(len(num_cols), 9)
    cols = 3; rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(12, 3 * rows))
    axes = axes.flatten() if n > 1 else [axes]

    for i, col in enumerate(num_cols[:n]):
        axes[i].hist(df[col].dropna(), bins=30, color="#42a5f5", edgecolor="#fff", alpha=0.85)
        axes[i].set_title(col, fontsize=10)
        axes[i].tick_params(labelsize=8)

    for j in range(n, len(axes)):
        axes[j].set_visible(False)

    plt.tight_layout()
    fig.savefig(os.path.join(out_dir, "distribution.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)
    _图表列表.append(os.path.join(out_dir, "distribution.png"))
    print("分布图已保存")

# %% [markdown]
# ### 热力图

# %%
if len(num_cols) >= 2:
    top = num_cols[:12]
    corr = df[top].corr()
    fig, ax = plt.subplots(figsize=(max(8, len(top) * 0.6), max(6, len(top) * 0.5)))
    im = ax.imshow(corr, cmap="RdYlBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(top))); ax.set_yticks(range(len(top)))
    ax.set_xticklabels(top, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(top, fontsize=8)
    fig.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title("相关系数热力图", fontsize=11)
    plt.tight_layout()
    fig.savefig(os.path.join(out_dir, "heatmap.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)
    _图表列表.append(os.path.join(out_dir, "heatmap.png"))
    print("热力图已保存")

# %% [markdown]
# ### 箱线图

# %%
if num_cols:
    top = num_cols[:10]
    sample = df[top].dropna()
    if len(sample) > 0:
        fig, ax = plt.subplots(figsize=(max(8, len(top) * 0.6), 5))
        bp = ax.boxplot([sample[c].values for c in top], labels=top, patch_artist=True,
                        flierprops=dict(marker="o", markersize=3, alpha=0.5))
        for patch in bp["boxes"]:
            patch.set_facecolor("#42a5f5"); patch.set_alpha(0.6)
        ax.tick_params(labelsize=8)
        ax.set_title("箱线图（异常值检测）", fontsize=11)
        plt.tight_layout()
        fig.savefig(os.path.join(out_dir, "boxplot.png"), dpi=120, bbox_inches="tight")
        plt.close(fig)
        _图表列表.append(os.path.join(out_dir, "boxplot.png"))
        print("箱线图已保存")

# 保存清洗后数据
clean_path = os.path.join(out_dir, "cleaned.csv")
df.to_csv(clean_path, index=False, encoding="utf-8-sig")
print(f"清洗后数据已保存 -> {clean_path}")

# Agent 用：输出图表路径，registry 自动 base64 嵌入
if _图表列表:
    print(f"__IMAGES__:{','.join(_图表列表)}")
