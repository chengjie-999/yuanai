# %% [markdown]
# # 数据预处理
# 缺失值处理 + 异常值检测 + 标准化/归一化 + 分类编码 + 特征选择。

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

__script_name__ = "数据预处理"
__script_desc__ = "对数据集执行数据预处理：缺失值填充、异常值检测（Z-score/IQR）、标准化/归一化、分类编码、低方差特征过滤。参数: dataset_id(必填), operations(missing,outlier,scale,encode,select默认全做), target_col(可选, 有监督预处理时指定目标列)"
__script_tags__ = ["数据清洗"]
__script_params__ = ["dataset_id", "operations", "target_col"]

_图表列表 = []
_HTML列表 = []

# %% [markdown]
# ### 参数

# %%
数据集ID = int(sys.argv[1]) if len(sys.argv) > 1 else 1
操作列表 = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else ["missing", "outlier", "scale", "encode", "select"]
目标列 = sys.argv[3] if len(sys.argv) > 3 else ""

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

原始行数 = len(df)
原始列数 = len(df.columns)
print(f"数据集 #{数据集ID}「{ds['name']}」: {原始行数} 行, {原始列数} 列")

预处理日志 = []
数值列 = df.select_dtypes(include=[np.number]).columns.tolist()
分类列 = df.select_dtypes(include=["object", "category"]).columns.tolist()

# %% [markdown]
# ### 1. 缺失值处理

# %%
if "missing" in 操作列表:
    缺失前 = df.isnull().sum().sum()
    if 缺失前 > 0:
        for col in 数值列:
            missing = df[col].isnull().sum()
            if missing > 0:
                df[col] = df[col].fillna(df[col].median())
                预处理日志.append(f"数值列「{col}」缺失 {missing} 个值，已用中位数填充")
        for col in 分类列:
            missing = df[col].isnull().sum()
            if missing > 0:
                df[col] = df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else "未知")
                预处理日志.append(f"分类列「{col}」缺失 {missing} 个值，已用众数填充")
        print(f"缺失值处理: {缺失前} → {df.isnull().sum().sum()}")
    else:
        print("无缺失值")

    原始行数2 = len(df)
    df = df.dropna(how="all").reset_index(drop=True)
    if len(df) < 原始行数2:
        预处理日志.append(f"去除 {原始行数2 - len(df)} 行全空行")

# %% [markdown]
# ### 缺失值热力图（处理前）

# %%
if "missing" in 操作列表:
    图表目录 = os.path.join(root_path(), "data", "analysis", "preprocess", str(数据集ID))
    os.makedirs(图表目录, exist_ok=True)

    fig, ax = plt.subplots(figsize=(max(8, len(df.columns) * 0.4), max(4, len(df.columns) * 0.2)))
    # 用原始数据的缺失信息画图
    缺失矩阵 = df.isnull()
    sns.heatmap(缺失矩阵.astype(int), cmap=["#e8f5e9", "#d32f2f"], cbar=False,
                yticklabels=False, ax=ax)
    ax.set_title("缺失值分布（处理后）", fontsize=11)
    ax.set_xlabel("列")
    plt.tight_layout()
    缺失热力路径 = os.path.join(图表目录, "missing_heatmap.png")
    fig.savefig(缺失热力路径, dpi=120, bbox_inches="tight")
    plt.close(fig)
    _图表列表.append(缺失热力路径)
    print("缺失值热力图已保存")

# %% [markdown]
# ### 2. 异常值检测

# %%
异常值统计 = {}
if "outlier" in 操作列表:
    for col in 数值列:
        col_data = df[col].dropna()
        if len(col_data) < 10:
            continue

        # Z-score 方法
        z_scores = np.abs((col_data - col_data.mean()) / col_data.std())
        z_outliers = (z_scores > 3).sum()

        # IQR 方法
        Q1, Q3 = col_data.quantile(0.25), col_data.quantile(0.75)
        IQR = Q3 - Q1
        lower, upper = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
        iqr_outliers = ((col_data < lower) | (col_data > upper)).sum()

        total_outliers = max(z_outliers, iqr_outliers)
        if total_outliers > 0:
            异常值统计[col] = {"Z-score异常": int(z_outliers), "IQR异常": int(iqr_outliers),
                          "Z下限": round(col_data.mean() - 3 * col_data.std(), 2),
                          "Z上限": round(col_data.mean() + 3 * col_data.std(), 2)}
            预处理日志.append(f"列「{col}」: Z-score {z_outliers} / IQR {iqr_outliers} 个异常值")

    if 异常值统计:
        print(f"检测到 {len(异常值统计)} 列含异常值（仅报告，不自动删除）")

# %% [markdown]
# ### 异常值箱线图（Top 10）

# %%
if "outlier" in 操作列表 and 数值列:
    绘图列 = 数值列[:min(len(数值列), 10)]
    fig, ax = plt.subplots(figsize=(max(8, len(绘图列) * 0.6), 5))
    df_melt = df[绘图列].melt(var_name="列", value_name="值")
    sns.boxplot(data=df_melt, x="列", y="值", palette="Set2", ax=ax)
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.set_title("异常值检测 — 箱线图", fontsize=11)
    plt.tight_layout()
    箱线图路径 = os.path.join(图表目录, "outlier_boxplot.png")
    fig.savefig(箱线图路径, dpi=120, bbox_inches="tight")
    plt.close(fig)
    _图表列表.append(箱线图路径)
    print("异常值箱线图已保存")

# %% [markdown]
# ### 3. 标准化 / 归一化

# %%
缩放信息 = {}
if "scale" in 操作列表 and 数值列:
    from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler

    非目标数值列 = [c for c in 数值列 if c != 目标列]
    if not 非目标数值列:
        非目标数值列 = 数值列

    # 默认使用 StandardScaler
    scaler = StandardScaler()
    原始值 = df[非目标数值列].copy()
    df[非目标数值列] = scaler.fit_transform(df[非目标数值列].fillna(0))
    for i, col in enumerate(非目标数值列):
        缩放信息[col] = {"mean_before": round(float(原始值[col].mean()), 2),
                      "std_before": round(float(原始值[col].std()), 2),
                      "mean_after": 0.0, "std_after": 1.0}
    预处理日志.append(f"标准化: {len(非目标数值列)} 列 (StandardScaler, mean=0 std=1)")
    print(f"标准化完成: {len(非目标数值列)} 列")

# %% [markdown]
# ### 标准化前后分布对比

# %%
if "scale" in 操作列表 and len(非目标数值列) >= 2:
    对比列 = 非目标数值列[:min(len(非目标数值列), 4)]
    fig, axes = plt.subplots(2, len(对比列), figsize=(4 * len(对比列), 7))
    if len(对比列) == 1:
        axes = axes.reshape(2, 1)

    for i, col in enumerate(对比列):
        axes[0, i].hist(原始值[col].dropna(), bins=30, color="#42a5f5", alpha=0.7, edgecolor="#fff")
        axes[0, i].set_title(f"{col} (原始)", fontsize=9)
        axes[0, i].tick_params(labelsize=7)

        axes[1, i].hist(df[col].dropna(), bins=30, color="#66bb6a", alpha=0.7, edgecolor="#fff")
        axes[1, i].set_title(f"{col} (标准化后)", fontsize=9)
        axes[1, i].tick_params(labelsize=7)

    fig.suptitle("标准化前后分布对比", fontsize=12, fontweight="bold")
    plt.tight_layout()
    缩放对比路径 = os.path.join(图表目录, "scale_comparison.png")
    fig.savefig(缩放对比路径, dpi=120, bbox_inches="tight")
    plt.close(fig)
    _图表列表.append(缩放对比路径)
    print("标准化对比图已保存")

# %% [markdown]
# ### 4. 分类变量编码

# %%
编码信息 = {}
if "encode" in 操作列表 and 分类列:
    from sklearn.preprocessing import LabelEncoder

    非目标分类列 = [c for c in 分类列 if c != 目标列]
    for col in 非目标分类列:
        unique_n = df[col].nunique()
        if unique_n <= 50:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
            编码信息[col] = {"原始类别数": unique_n, "编码方式": "LabelEncoder"}
            预处理日志.append(f"分类列「{col}」: {unique_n} 类 → LabelEncoder")
        else:
            编码信息[col] = {"原始类别数": unique_n, "编码方式": "跳过（>50类）"}
            预处理日志.append(f"分类列「{col}」: {unique_n} 类 → 跳过高基数列")

    if 编码信息:
        print(f"分类编码完成: {sum(1 for v in 编码信息.values() if v['编码方式'] != '跳过（>50类）')} 列")

# %% [markdown]
# ### 5. 低方差特征过滤

# %%
过滤列 = []
if "select" in 操作列表 and 数值列:
    from sklearn.feature_selection import VarianceThreshold

    非目标数值列2 = [c for c in 数值列 if c != 目标列]
    if len(非目标数值列2) > 1:
        selector = VarianceThreshold(threshold=0.01)
        X_subset = df[非目标数值列2].fillna(0)
        selector.fit(X_subset)
        保留掩码 = selector.get_support()
        过滤列 = [非目标数值列2[i] for i in range(len(非目标数值列2)) if not 保留掩码[i]]

        if 过滤列:
            df = df.drop(columns=过滤列)
            预处理日志.append(f"低方差过滤: 删除 {len(过滤列)} 列 — {', '.join(过滤列)}")
            print(f"低方差过滤: 删除 {len(过滤列)} 列")
        else:
            print("低方差过滤: 无需删除的列")

# %% [markdown]
# ### 保存清洗后数据

# %%
清洗目录 = os.path.join(root_path(), "data", "analysis", str(数据集ID))
os.makedirs(清洗目录, exist_ok=True)
清洗路径 = os.path.join(清洗目录, "cleaned.csv")
df.to_csv(清洗路径, index=False, encoding="utf-8-sig")
print(f"清洗后数据已保存 -> {清洗路径}")

# %% [markdown]
# ### plotly 交互式缺失值矩阵

# %%
if "missing" in 操作列表:
    import plotly.graph_objects as go
    import plotly.express as px

    缺失数据 = df.isnull().sum().reset_index()
    缺失数据.columns = ["列", "缺失数"]
    缺失数据 = 缺失数据[缺失数据["缺失数"] > 0]
    if len(缺失数据) > 0:
        缺失数据["缺失率"] = (缺失数据["缺失数"] / len(df) * 100).round(1)
        fig = px.bar(缺失数据.sort_values("缺失率", ascending=True),
                     x="缺失率", y="列", orientation="h",
                     title="各列缺失率（处理后）",
                     text="缺失率",
                     color="缺失率", color_continuous_scale="Reds")
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        fig.update_layout(height=max(200, len(缺失数据) * 25), margin=dict(l=20, r=40, t=50, b=20))
        HTML缺失路径 = os.path.join(图表目录, "missing_interactive.html")
        fig.write_html(HTML缺失路径, include_plotlyjs="cdn", full_html=True,
                       config={"displayModeBar": True, "responsive": True})
        _HTML列表.append(HTML缺失路径)
        print("交互式缺失率图已保存")

# %% [markdown]
# ### 输出标记

# %%
print(f"\n## 预处理摘要")
print(f"原始: {原始行数} 行 × {原始列数} 列")
print(f"处理后: {len(df)} 行 × {len(df.columns)} 列")
for log in 预处理日志:
    print(f"  {log}")

if _图表列表:
    print(f"__IMAGES__:{','.join(_图表列表)}")
if _HTML列表:
    print(f"__HTML__:{','.join(_HTML列表)}")

import json as _json
_result = {
    "original_shape": [原始行数, 原始列数],
    "cleaned_shape": [len(df), len(df.columns)],
    "cleaned_path": 清洗路径,
    "logs": 预处理日志,
    "outliers": 异常值统计,
    "scaling": 缩放信息,
    "encoding": 编码信息,
    "removed_low_variance": 过滤列,
}
print(f"__RESULT__:{_json.dumps(_result, ensure_ascii=False)}")
