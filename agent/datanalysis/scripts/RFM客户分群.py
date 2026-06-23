# %% [markdown]
# # RFM 客户价值分群
# 从订单明细计算每个客户的 R（最近交易间隔）、F（交易频次）、M（累计金额），
# 基于均值二分法打分，输出 8 类客户标签。

# %%
import os, sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# PyCharm 科学模式或命令行运行时需要项目根在 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from utils.data_path import root_path

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

# ═══════════════════════════════════
# Agent 发现用（不影响脚本独立运行）
# ═══════════════════════════════════
__script_name__ = "RFM客户分群"
__script_desc__ = "从订单明细 Excel 中计算客户 RFM 价值分群。参数: file_path(必填, 含「用户编号」「交易时间」「金额」), user_info_path(可选, 含「用户编号」「区域」用于下钻)"
__script_params__ = ["file_path", "user_info_path"]

# %% [markdown]
# ### 参数
# PyCharm 中直接修改下面值后逐块运行；Agent 通过命令行传入。

# %%
文件路径 = sys.argv[1] if len(sys.argv) > 1 else "data/user/from/订单明细.xlsx"
用户信息路径 = sys.argv[2] if len(sys.argv) > 2 else ""

# %%
full_path = os.path.join(root_path(), 文件路径)
if not os.path.exists(full_path):
    raise FileNotFoundError(f"文件不存在: {full_path}")

df = pd.read_excel(full_path) if full_path.endswith(".xlsx") else pd.read_csv(full_path)

required = ["用户编号", "交易时间", "金额"]
missing = [c for c in required if c not in df.columns]
if missing:
    raise ValueError(f"缺少必要列: {missing}。订单表需包含「用户编号」「交易时间」「金额」")

print(f"已加载: {full_path}")
df.head()

# %% [markdown]
# ### 数据清洗

# %%
total_orders = len(df)
if "交易状态" in df.columns:
    df = df[df["交易状态"] == "交易成功"]
df["交易时间"] = pd.to_datetime(df["交易时间"])
df = df[["用户编号", "交易时间", "金额"]].dropna()
print(f"清洗: {total_orders} -> {len(df)} 条")

# %% [markdown]
# ### 计算 R / F / M

# %%
参考日期 = df["交易时间"].max()

# R：最近一次交易距参考日期的天数（越小越好）
r = df.groupby("用户编号")["交易时间"].max().reset_index()
r["R"] = (参考日期 - r["交易时间"]).dt.days
r = r[["用户编号", "R"]]

# F：交易频次 — 不同日期的交易天数（越大越好）
f = df.groupby("用户编号").agg(F=("交易时间", "nunique")).reset_index()

# M：累计交易金额（越大越好）
m = df.groupby("用户编号").agg(M=("金额", "sum")).reset_index()

rfm = r.merge(f, on="用户编号").merge(m, on="用户编号")
print(f"用户数: {len(rfm)}")
rfm.head()

# %% [markdown]
# ### 打分

# %%
n_users = len(rfm)
均值R, 均值F, 均值M = rfm["R"].mean(), rfm["F"].mean(), rfm["M"].mean()

标签映射 = {
    111: "重要价值", 110: "一般价值",
    101: "重要发展", 100: "一般发展",
    11:  "重要保持", 10:  "一般保持",
    1:   "重要挽留", 0:   "一般挽留",
}

rfm["R_score"] = (rfm["R"] < 均值R) * 100
rfm["F_score"] = (rfm["F"] > 均值F) * 10
rfm["M_score"] = (rfm["M"] > 均值M) * 1
rfm["总分"] = rfm["R_score"] + rfm["F_score"] + rfm["M_score"]
rfm["用户标签"] = rfm["总分"].map(标签映射)
rfm[["用户编号", "R", "F", "M", "总分", "用户标签"]].head()

# %% [markdown]
# ### 汇总统计

# %%
人数 = rfm["用户标签"].value_counts().reset_index()
人数.columns = ["用户标签", "人数"]
人数["人数占比"] = (人数["人数"] / 人数["人数"].sum()).apply(lambda x: f"{x:.1%}")

金额 = rfm.groupby("用户标签")["M"].sum().reset_index()
金额.columns = ["用户标签", "金额"]
金额["金额占比"] = (金额["金额"] / 金额["金额"].sum()).apply(lambda x: f"{x:.1%}")

汇总表 = 人数.merge(金额, on="用户标签").sort_values(["金额", "人数"], ascending=[False, False])

print(f"\n## RFM 客户价值分群")
print(f"用户数: {n_users}  ·  订单数: {len(df)}  ·  参考日期: {参考日期.date()}")
print(f"均值 — R: {均值R:.1f}天  F: {均值F:.1f}次  M: ￥{均值M:,.0f}")
print(f"\n### 各群人数与金额")
print(汇总表.to_string(index=False))

# %% [markdown]
# ### 区域下钻（可选）

# %%
if 用户信息路径:
    user_full = os.path.join(root_path(), 用户信息路径)
    if os.path.exists(user_full):
        user = pd.read_excel(user_full) if user_full.endswith(".xlsx") else pd.read_csv(user_full)
        if "用户编号" in user.columns and "区域" in user.columns:
            rfm_user = rfm.merge(user[["用户编号", "区域"]], on="用户编号")
            区域统计 = rfm_user.groupby(["区域", "用户标签"]).agg(
                人数=("用户编号", "count"), 金额=("M", "sum")
            ).reset_index().sort_values(["区域", "金额"], ascending=[True, False])
            print("\n### 区域分布")
            print(区域统计.to_string(index=False))

# %% [markdown]
# ### 分布图

# %%
fig_dir = os.path.join(root_path(), "data", "analysis", "rfm")
os.makedirs(fig_dir, exist_ok=True)

fig, axes = plt.subplots(1, 3, figsize=(16, 4))
for ax, col, title, color in zip(
    axes,
    ["R", "F", "M"],
    ["R 最近交易间隔(天)", "F 交易频次", "M 累计金额"],
    ["#e53935", "#43a047", "#1e88e5"],
):
    sns.kdeplot(data=rfm, x=col, fill=True, alpha=0.3, color=color, ax=ax)
    均值 = rfm[col].mean()
    ax.axvline(均值, color=color, linestyle="--", linewidth=2)
    ax.set_title(f"{title}\n均值={均值:.1f}", fontsize=10)
    ax.text(0.95, 0.95, f"偏度={rfm[col].skew():.2f}",
            transform=ax.transAxes, ha="right", va="top", fontsize=8, color="#999")

plt.tight_layout()
rfm_png = os.path.join(fig_dir, "rfm_distribution.png")
fig.savefig(rfm_png, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"分布图已保存 -> {rfm_png}")
print(f"__IMAGES__:{rfm_png}")
