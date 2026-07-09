# %% [markdown]
# # RFM 客户价值分群
# 从订单明细计算每个客户的 R（最近交易间隔）、F（交易频次）、M（累计金额），
# 基于百分位打分，输出 8 类客户标签 + 3D 交互散点 + pairplot 关系探索。

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
__script_desc__ = "从订单明细 Excel 计算客户 RFM 价值分群（百分位打分 + 3D散点 + 分群关系图）。file_path 默认使用 data/user/from/订单明细.xlsx（已内置示例数据），无需用户提供即可直接运行。user_info_path 可选用于区域下钻"
__script_tags__ = ["客户分析"]
__script_params__ = ["file_path", "user_info_path"]

_图表列表 = []
_HTML列表 = []

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
# ### 百分位打分（替代均值二分法）
# 使用 numpy 百分位：R 越低分越高（越活跃），F/M 越高分越高

# %%
n_users = len(rfm)

# 百分位打分：R 反转（最近 > 80 分位 → 高分），F/M 正向（高值 → 高分）
R_percentile = rfm["R"].rank(pct=True) * 100
F_percentile = rfm["F"].rank(pct=True) * 100
M_percentile = rfm["M"].rank(pct=True) * 100

# 均值二分法（保持兼容）
均值R, 均值F, 均值M = rfm["R"].mean(), rfm["F"].mean(), rfm["M"].mean()

# 百分位阀值（中位数 = 50 分位）
R_median, F_median, M_median = rfm["R"].median(), rfm["F"].median(), rfm["M"].median()

标签映射 = {
    111: "重要价值", 110: "一般价值",
    101: "重要发展", 100: "一般发展",
    11:  "重要保持", 10:  "一般保持",
    1:   "重要挽留", 0:   "一般挽留",
}

# 均值二分法打分（保持向后兼容）
rfm["R_score"] = (rfm["R"] < 均值R) * 100
rfm["F_score"] = (rfm["F"] > 均值F) * 10
rfm["M_score"] = (rfm["M"] > 均值M) * 1
rfm["总分"] = rfm["R_score"] + rfm["F_score"] + rfm["M_score"]
rfm["用户标签"] = rfm["总分"].map(标签映射)

# 百分位分数（0-100）
rfm["R_pct"] = (100 - R_percentile).round(0)  # R越低越好，反转
rfm["F_pct"] = F_percentile.round(0)
rfm["M_pct"] = M_percentile.round(0)
rfm["百分位总分"] = (rfm["R_pct"] + rfm["F_pct"] + rfm["M_pct"]).round(0)

rfm[["用户编号", "R", "F", "M", "用户标签", "R_pct", "F_pct", "M_pct", "百分位总分"]].head()

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
print(f"中位数 — R: {R_median:.1f}天  F: {F_median:.1f}次  M: ￥{M_median:,.0f}")
print(f"\n### 各群人数与金额")
print(汇总表.to_string(index=False))

# %% [markdown]
# ### 区域下钻（可选）

# %%
区域统计 = None
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
# ### 图表目录

# %%
fig_dir = os.path.join(root_path(), "data", "analysis", "rfm")
os.makedirs(fig_dir, exist_ok=True)

# %% [markdown]
# ### seaborn 分布图 — R/F/M kdeplot

# %%
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
_图表列表.append(rfm_png)
print(f"分布图已保存 -> {rfm_png}")

# %% [markdown]
# ### seaborn pairplot — R/F/M 按分群着色

# %%
样本 = rfm.sample(min(500, len(rfm)), random_state=42)
g = sns.pairplot(样本, vars=["R", "F", "M"], hue="用户标签",
                 palette="Set2", diag_kind="kde",
                 plot_kws={"alpha": 0.4, "s": 12},
                 diag_kws={"fill": True, "alpha": 0.4})
g.fig.suptitle("R/F/M 分群关系 (Pairplot)", y=1.01, fontsize=13)
pairplot_png = os.path.join(fig_dir, "rfm_pairplot.png")
g.fig.savefig(pairplot_png, dpi=120, bbox_inches="tight")
plt.close("all")
_图表列表.append(pairplot_png)
print("RFM Pairplot 已保存")

# %% [markdown]
# ### seaborn 分群柱状图 — 人数 + 金额

# %%
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
seg_order = 汇总表.sort_values("人数", ascending=True)

colors1 = ["#1e88e5" if "价值" in l else "#66bb6a" if "发展" in l else "#ffa726" if "保持" in l else "#ef5350"
           for l in seg_order["用户标签"]]
ax1.barh(seg_order["用户标签"], seg_order["人数"], color=colors1, alpha=0.85)
ax1.set_title("各分群人数", fontsize=10)
ax1.set_xlabel("人数")

seg_order2 = 汇总表.sort_values("金额", ascending=True)
colors2 = ["#1e88e5" if "价值" in l else "#66bb6a" if "发展" in l else "#ffa726" if "保持" in l else "#ef5350"
           for l in seg_order2["用户标签"]]
ax2.barh(seg_order2["用户标签"], seg_order2["金额"], color=colors2, alpha=0.85)
ax2.set_title("各分群累计金额", fontsize=10)
ax2.set_xlabel("金额（元）")

plt.tight_layout()
bar_png = os.path.join(fig_dir, "rfm_segments.png")
fig.savefig(bar_png, dpi=120, bbox_inches="tight")
plt.close(fig)
_图表列表.append(bar_png)
print("分群柱状图已保存")

# %% [markdown]
# ### plotly 交互式 3D 散点图

# %%
import plotly.graph_objects as go

SEGMENT_COLORS = {
    "重要价值": "#1a73e8", "一般价值": "#4285f4",
    "重要发展": "#f9a825", "一般发展": "#fbc02d",
    "重要保持": "#0d904f", "一般保持": "#34a853",
    "重要挽留": "#d93025", "一般挽留": "#ea4335",
}

sample_3d = rfm.head(500)
fig = go.Figure(data=[go.Scatter3d(
    x=sample_3d["R"], y=sample_3d["F"], z=sample_3d["M"],
    mode="markers",
    marker=dict(size=4, color=sample_3d["用户标签"].map(SEGMENT_COLORS), opacity=0.8),
    text=sample_3d["用户编号"].astype(str) + "<br>" + sample_3d["用户标签"],
    hoverinfo="text",
)])
fig.update_layout(
    scene=dict(xaxis_title="R (间隔天数)", yaxis_title="F (交易频次)", zaxis_title="M (累计金额)",
               bgcolor="#16213e"),
    paper_bgcolor="#16213e", font_color="#eaeaea",
    height=500, margin=dict(l=0, r=0, t=0, b=0),
    title="RFM 3D 客户分群",
)
html_3d_path = os.path.join(fig_dir, "rfm_3d_interactive.html")
fig.write_html(html_3d_path, include_plotlyjs="cdn", full_html=True,
               config={"displayModeBar": True, "responsive": True})
_HTML列表.append(html_3d_path)
print("3D 交互散点图已保存")

# %% [markdown]
# ### plotly 交互式分群柱状图

# %%
import plotly.graph_objects as go
from plotly.subplots import make_subplots

fig = make_subplots(rows=1, cols=2, subplot_titles=("各分群人数", "各分群金额占比"),
                    specs=[[{"type": "bar"}, {"type": "pie"}]])

fig.add_trace(go.Bar(
    x=汇总表["人数"], y=汇总表["用户标签"], orientation="h",
    marker_color=[SEGMENT_COLORS.get(l, "#999") for l in 汇总表["用户标签"]],
    text=汇总表["人数占比"], textposition="outside",
    hovertemplate="%{y}: %{x}人<extra></extra>",
), row=1, col=1)

fig.add_trace(go.Pie(
    labels=汇总表["用户标签"], values=汇总表["金额"],
    marker_colors=[SEGMENT_COLORS.get(l, "#999") for l in 汇总表["用户标签"]],
    hole=0.35, textinfo="label+percent",
), row=1, col=2)

fig.update_layout(height=400, showlegend=False, margin=dict(l=20, r=20, t=50, b=20),
                  template="plotly_white")
html_seg_path = os.path.join(fig_dir, "rfm_segments_interactive.html")
fig.write_html(html_seg_path, include_plotlyjs="cdn", full_html=True,
               config={"displayModeBar": True, "responsive": True})
_HTML列表.append(html_seg_path)
print("交互式分群图已保存")

# %% [markdown]
# ### 输出标记

# %%
if _图表列表:
    print(f"__IMAGES__:{','.join(_图表列表)}")
if _HTML列表:
    print(f"__HTML__:{','.join(_HTML列表)}")

import json as _json
_result = {
    "summary": {"用户数": n_users, "订单数": len(df), "参考日期": str(参考日期.date())},
    "means": {"R均值(天)": round(均值R, 1), "F均值(次)": round(均值F, 1), "M均值(元)": round(均值M, 0)},
    "medians": {"R中位数(天)": round(R_median, 1), "F中位数(次)": round(F_median, 1), "M中位数(元)": round(M_median, 0)},
    "segments": [
        {"label": row["用户标签"], "count": int(row["人数"]), "count_pct": row["人数占比"],
         "amount": int(row["金额"]), "amount_pct": row["金额占比"]}
        for _, row in 汇总表.iterrows()
    ],
    "scoring": "百分位+均值双方法",
}
print(f"__RESULT__:{_json.dumps(_result, ensure_ascii=False)}")
