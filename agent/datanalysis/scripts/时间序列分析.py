# %% [markdown]
# # 时间序列分析
# 趋势分解 + 季节性检测 + 滚动统计 + 异常检测 + ADF平稳性检验。

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

__script_name__ = "时间序列分析"
__script_desc__ = "对含日期列的数据集做时间序列分析：趋势分解(STL)、滚动统计、异常检测、ADF平稳性检验、自相关图。参数: dataset_id(必填, 数据集ID), date_col(可选, 自动检测), value_col(可选, 自动选第一个数值列), period(可选, 季节性周期，默认7)"
__script_tags__ = ["统计分析", "时间序列"]
__script_params__ = ["dataset_id", "date_col", "value_col", "period"]

_图表列表 = []
_HTML列表 = []

# %% [markdown]
# ### 参数

# %%
数据集ID = int(sys.argv[1]) if len(sys.argv) > 1 else 1
指定日期列 = sys.argv[2] if len(sys.argv) > 2 else ""
指定数值列 = sys.argv[3] if len(sys.argv) > 3 else ""
周期 = int(sys.argv[4]) if len(sys.argv) > 4 else 7

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
# ### 日期列自动检测

# %%
if 指定日期列 and 指定日期列 in df.columns:
    日期列 = 指定日期列
else:
    # 自动检测日期列
    日期列 = ""
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in ("date", "time", "日期", "时间", "timestamp")):
            try:
                df[col] = pd.to_datetime(df[col])
                日期列 = col
                break
            except Exception:
                pass

if not 日期列:
    raise ValueError(f"未检测到日期列，可用列: {list(df.columns)}。请通过 date_col 参数指定。")

try:
    df[日期列] = pd.to_datetime(df[日期列])
except Exception:
    raise ValueError(f"列「{日期列}」无法转为日期格式")

print(f"日期列: {日期列}, 范围: {df[日期列].min().date()} ~ {df[日期列].max().date()}")

# %% [markdown]
# ### 数值列选择

# %%
数值列列表 = df.select_dtypes(include=[np.number]).columns.tolist()
数值列列表 = [c for c in 数值列列表 if c != 日期列]

if 指定数值列 and 指定数值列 in 数值列列表:
    数值列 = 指定数值列
elif 数值列列表:
    数值列 = 数值列列表[0]
else:
    raise ValueError("无可用数值列")

print(f"分析列: {数值列}")

# %% [markdown]
# ### 数据准备

# %%
df_ts = df[[日期列, 数值列]].copy()
df_ts = df_ts.dropna(subset=[日期列, 数值列])
df_ts = df_ts.sort_values(日期列)
df_ts = df_ts.set_index(日期列)

序列 = df_ts[数值列].dropna()
if len(序列) < 14:
    raise ValueError(f"时间序列太短（需要至少14个观测点），当前: {len(序列)}")

# 重采样到日频（如有重复取均值）
序列 = 序列.resample("D").mean().interpolate(method="linear").dropna()

print(f"有效观测: {len(序列)}, 范围: {序列.index[0].date()} ~ {序列.index[-1].date()}")

# %% [markdown]
# ### 基础统计

# %%
趋势方向 = "上升" if 序列.iloc[-1] > 序列.iloc[0] else "下降"
变化率 = (序列.iloc[-1] - 序列.iloc[0]) / abs(序列.iloc[0]) * 100 if 序列.iloc[0] != 0 else 0
总均值 = float(序列.mean())
总标准差 = float(序列.std())
变异系数 = round(总标准差 / 总均值 * 100, 1) if 总均值 != 0 else 0

print(f"\n## 基本统计")
print(f"观测数: {len(序列)}")
print(f"均值: {总均值:.2f}  ·  标准差: {总标准差:.2f}  ·  CV: {变异系数}%")
print(f"趋势: {趋势方向}  ·  总变化率: {变化率:.1f}%")
print(f"最小值: {序列.min():.2f} ({序列.idxmin().date()})")
print(f"最大值: {序列.max():.2f} ({序列.idxmax().date()})")

# %% [markdown]
# ### 滚动统计（7日窗口）

# %%
滚动均值 = 序列.rolling(7, min_periods=1).mean()
滚动标准差 = 序列.rolling(7, min_periods=1).std()
print(f"7日滚动均值: 最新 {滚动均值.iloc[-1]:.2f}")
print(f"7日滚动标准差: 最新 {滚动标准差.iloc[-1]:.2f}")

# %% [markdown]
# ### ADF 平稳性检验

# %%
from statsmodels.tsa.stattools import adfuller

adf_result = adfuller(序列.dropna(), autolag="AIC")
print(f"\n## ADF 平稳性检验")
print(f"ADF 统计量: {adf_result[0]:.4f}")
print(f"p 值: {adf_result[1]:.4f}")
print(f"临界值: 1%={adf_result[4]['1%']:.4f}, 5%={adf_result[4]['5%']:.4f}, 10%={adf_result[4]['10%']:.4f}")
print(f"结论: {'平稳 ✅' if adf_result[1] < 0.05 else '非平稳 ⚠️（建议差分）'}")
是否平稳 = adf_result[1] < 0.05

# %% [markdown]
# ### STL 分解

# %%
分解结果 = None
try:
    from statsmodels.tsa.seasonal import STL

    有效周期 = min(周期, max(2, len(序列) // 4))
    stl = STL(序列.dropna(), period=有效周期, robust=True).fit()
    分解结果 = {
        "date": [d.isoformat() for d in 序列.index],
        "trend": [float(v) if not np.isnan(v) else None for v in stl.trend.values],
        "seasonal": [float(v) if not np.isnan(v) else None for v in stl.seasonal.values],
        "resid": [float(v) if not np.isnan(v) else None for v in stl.resid.values],
    }
    季节强度 = 1 - np.var(stl.resid.dropna()) / np.var((stl.trend + stl.seasonal).dropna())
    print(f"\n## STL 分解 (period={有效周期})")
    print(f"季节强度: {季节强度:.3f} ({'强季节性' if 季节强度 > 0.3 else '弱季节性'})")
    print(f"趋势长度: {len(stl.trend.dropna())}")
except Exception as e:
    print(f"STL 分解失败: {e}")

# %% [markdown]
# ### 异常检测（滚动 Z-score）

# %%
异常点列表 = []
try:
    roll_m = 序列.rolling(14, min_periods=7).mean()
    roll_s = 序列.rolling(14, min_periods=7).std().replace(0, np.nan)
    z_scores = ((序列 - roll_m) / roll_s).dropna()
    异常点 = z_scores[z_scores.abs() > 3]
    if len(异常点) > 0:
        异常点列表 = [
            {"date": d.isoformat(), "value": round(float(序列[d]), 2), "z_score": round(float(z_scores[d]), 2)}
            for d in 异常点.index
        ]
        print(f"\n## 异常点 ({len(异常点列表)} 个, |Z|>3)")
        for pt in 异常点列表[:10]:
            print(f"  {pt['date'][:10]}: {pt['value']:.2f} (z={pt['z_score']:.2f})")
except Exception as e:
    print(f"异常检测失败: {e}")

# %% [markdown]
# ### 图表目录

# %%
图表目录 = os.path.join(root_path(), "data", "analysis", "timeseries", str(数据集ID))
os.makedirs(图表目录, exist_ok=True)

# %% [markdown]
# ### matplotlib 静态图：ACF / PACF

# %%
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
plot_acf(序列.dropna(), lags=min(40, len(序列)//4), ax=ax1)
ax1.set_title("自相关函数 (ACF)", fontsize=11)
plot_pacf(序列.dropna(), lags=min(40, len(序列)//4), ax=ax2, method="ywm")
ax2.set_title("偏自相关函数 (PACF)", fontsize=11)
plt.tight_layout()
ACF路径 = os.path.join(图表目录, "acf_pacf.png")
fig.savefig(ACF路径, dpi=120, bbox_inches="tight")
plt.close(fig)
_图表列表.append(ACF路径)
print("ACF/PACF 图已保存")

# %% [markdown]
# ### seaborn 季节性热力图（按星期几 × 周）

# %%
if len(序列) >= 28:
    周数据 = pd.DataFrame({"值": 序列.values}, index=序列.index)
    周数据["星期"] = 周数据.index.dayofweek
    周数据["周序号"] = 周数据.index.isocalendar().week
    周数据["月"] = 周数据.index.month

    热力数据 = 周数据.pivot_table(values="值", index="星期", columns="月", aggfunc="mean")
    星期标签 = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    fig, ax = plt.subplots(figsize=(10, 4))
    sns.heatmap(热力数据, annot=True, fmt=".1f", cmap="YlOrRd",
                xticklabels=[f"{m}月" for m in 热力数据.columns],
                yticklabels=[星期标签[i] for i in 热力数据.index if i < 7],
                ax=ax)
    ax.set_title(f"季节性热力图 — 星期几 × 月份 ({数值列})", fontsize=11)
    plt.tight_layout()
    季节热力路径 = os.path.join(图表目录, "seasonal_heatmap.png")
    fig.savefig(季节热力路径, dpi=120, bbox_inches="tight")
    plt.close(fig)
    _图表列表.append(季节热力路径)
    print("季节性热力图已保存")

# %% [markdown]
# ### plotly 交互式时序图（滚动均值 + 异常点）

# %%
import plotly.graph_objects as go
from plotly.subplots import make_subplots

fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                    subplot_titles=("时序 + 滚动均值 ± σ", "趋势 + 季节（STL）"),
                    vertical_spacing=0.12, row_heights=[0.55, 0.45])

# Row 1: 原始序列 + 滚动均值
fig.add_trace(go.Scatter(x=序列.index, y=序列.values, mode="lines",
                         name=数值列, line=dict(color="#589df6", width=1), opacity=0.5), row=1, col=1)
fig.add_trace(go.Scatter(x=滚动均值.index, y=滚动均值.values, mode="lines",
                         name="7日滚动均值", line=dict(color="#f5a623", width=2)), row=1, col=1)
# 滚动均值 ± 1σ 带
upper = (滚动均值 + 滚动标准差).values
lower = (滚动均值 - 滚动标准差).values
fig.add_trace(go.Scatter(
    x=list(滚动均值.index) + list(滚动均值.index[::-1]),
    y=list(upper) + list(lower[::-1]),
    fill="toself", fillcolor="rgba(245,166,35,0.15)", line=dict(width=0),
    name="±1σ", showlegend=True,
), row=1, col=1)

# 异常点标注
if 异常点列表:
    异常日期 = [pd.Timestamp(pt["date"]) for pt in 异常点列表]
    异常值 = [pt["value"] for pt in 异常点列表]
    fig.add_trace(go.Scatter(x=异常日期, y=异常值, mode="markers",
                             name="异常点", marker=dict(color="#ef5350", size=8, symbol="x")), row=1, col=1)

# Row 2: STL 趋势
if 分解结果:
    fig.add_trace(go.Scatter(x=序列.index, y=分解结果["trend"], mode="lines",
                             name="趋势", line=dict(color="#589df6", width=2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=序列.index, y=分解结果["seasonal"], mode="lines",
                             name="季节", line=dict(color="#66bb6a", width=1.5)), row=2, col=1)

fig.update_layout(height=600, margin=dict(l=20, r=20, t=50, b=20),
                  legend=dict(orientation="h", yanchor="top", y=-0.05),
                  hovermode="x unified",
                  template="plotly_white")
HTML时序路径 = os.path.join(图表目录, "timeseries_interactive.html")
fig.write_html(HTML时序路径, include_plotlyjs="cdn", full_html=True,
               config={"displayModeBar": True, "responsive": True})
_HTML列表.append(HTML时序路径)
print("交互式时序图已保存")

# %% [markdown]
# ### plotly 分解图（独立）

# %%
if 分解结果:
    fig2 = make_subplots(rows=3, cols=1, shared_xaxes=True,
                         subplot_titles=("趋势", "季节", "残差"), vertical_spacing=0.08)
    fig2.add_trace(go.Scatter(x=序列.index, y=分解结果["trend"], mode="lines",
                              line=dict(color="#589df6", width=1.5), name="趋势"), row=1, col=1)
    fig2.add_trace(go.Scatter(x=序列.index, y=分解结果["seasonal"], mode="lines",
                              line=dict(color="#66bb6a", width=1.5), name="季节"), row=2, col=1)
    fig2.add_trace(go.Scatter(x=序列.index, y=分解结果["resid"], mode="lines",
                              line=dict(color="#ef5350", width=1), name="残差"), row=3, col=1)
    fig2.update_layout(height=500, showlegend=False, margin=dict(l=20, r=20, t=50, b=20),
                       template="plotly_white")
    HTML分解路径 = os.path.join(图表目录, "decomposition.html")
    fig2.write_html(HTML分解路径, include_plotlyjs="cdn", full_html=True,
                    config={"displayModeBar": True, "responsive": True})
    _HTML列表.append(HTML分解路径)
    print("交互式分解图已保存")

# %% [markdown]
# ### 输出标记

# %%
if _图表列表:
    print(f"__IMAGES__:{','.join(_图表列表)}")
if _HTML列表:
    print(f"__HTML__:{','.join(_HTML列表)}")

import json as _json
_result = {
    "date_col": 日期列, "value_col": 数值列,
    "observations": len(序列),
    "mean": round(总均值, 2), "std": round(总标准差, 2), "cv_pct": 变异系数,
    "trend_direction": 趋势方向, "total_change_pct": round(变化率, 1),
    "min_value": round(float(序列.min()), 2), "max_value": round(float(序列.max()), 2),
    "is_stationary": 是否平稳, "adf_pvalue": round(adf_result[1], 4),
    "seasonal_strength": round(季节强度, 3) if 分解结果 else None,
    "anomalies": 异常点列表,
    "rolling_mean_latest": round(float(滚动均值.iloc[-1]), 2),
}
print(f"__RESULT__:{_json.dumps(_result, ensure_ascii=False)}")
