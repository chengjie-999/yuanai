# %% [markdown]
# # 回归分析
# 线性/岭/Lasso 回归建模 + 交叉验证 + 残差诊断 + 特征重要性。

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

__script_name__ = "回归分析"
__script_desc__ = "对数据集做回归建模分析：线性/岭回归/Lasso/多项式回归 + 交叉验证 + 残差诊断。参数: dataset_id(必填), target_col(必填, 目标列名), feature_cols(可选, 逗号分隔特征列，默认自动选数值列), model_type(linear/ridge/lasso/poly), test_size(默认0.2)"
__script_tags__ = ["统计分析", "机器学习"]
__script_params__ = ["dataset_id", "target_col", "feature_cols", "model_type", "test_size"]

_图表列表 = []
_HTML列表 = []

# %% [markdown]
# ### 参数

# %%
数据集ID = int(sys.argv[1]) if len(sys.argv) > 1 else 1
目标列名 = sys.argv[2] if len(sys.argv) > 2 else ""
特征列参数 = sys.argv[3] if len(sys.argv) > 3 else ""
模型类型 = sys.argv[4] if len(sys.argv) > 4 else "linear"
测试比例 = float(sys.argv[5]) if len(sys.argv) > 5 else 0.2

if not 目标列名:
    raise ValueError("必须指定 target_col（目标列名）")

if 模型类型 not in ("linear", "ridge", "lasso", "poly"):
    raise ValueError(f"不支持的模型类型: {模型类型}，可选 linear/ridge/lasso/poly")

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

if 目标列名 not in df.columns:
    raise ValueError(f"目标列「{目标列名}」不存在。可用列: {list(df.columns)}")

# %% [markdown]
# ### 特征选择

# %%
if 特征列参数:
    特征列表 = [c.strip() for c in 特征列参数.split(",")]
    missing = [c for c in 特征列表 if c not in df.columns]
    if missing:
        raise ValueError(f"特征列不存在: {missing}")
else:
    数值列列表 = df.select_dtypes(include=[np.number]).columns.tolist()
    特征列表 = [c for c in 数值列列表 if c != 目标列名]
    if len(特征列表) > 12:
        特征列表 = 特征列表[:12]

if len(特征列表) < 1:
    raise ValueError(f"可用特征列不足（需要至少 1 列），当前: {特征列表}")

# 处理缺失值
for col in 特征列表 + [目标列名]:
    if df[col].isnull().any():
        df[col] = df[col].fillna(df[col].median() if col in df.select_dtypes(include=[np.number]).columns else df[col].mode()[0])

print(f"目标列: {目标列名}  |  特征列 ({len(特征列表)}): {', '.join(特征列表)}")

# %% [markdown]
# ### 数据准备

# %%
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

X = df[特征列表].values
y = df[目标列名].values

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=测试比例, random_state=42)
print(f"训练集: {len(X_train)}  ·  测试集: {len(X_test)}")

# %% [markdown]
# ### 建模

# %%
if 模型类型 == "linear":
    model = Pipeline([("scaler", StandardScaler()), ("reg", LinearRegression())])
    模型名称 = "线性回归"
elif 模型类型 == "ridge":
    model = Pipeline([("scaler", StandardScaler()), ("reg", Ridge(alpha=1.0))])
    模型名称 = "岭回归 (α=1.0)"
elif 模型类型 == "lasso":
    model = Pipeline([("scaler", StandardScaler()), ("reg", Lasso(alpha=0.1, max_iter=5000))])
    模型名称 = "Lasso 回归 (α=0.1)"
elif 模型类型 == "poly":
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("poly", PolynomialFeatures(degree=2, include_bias=False)),
        ("reg", LinearRegression()),
    ])
    模型名称 = "多项式回归 (degree=2)"

model.fit(X_train, y_train)
print(f"模型: {模型名称} 训练完成")

# %% [markdown]
# ### 评估

# %%
y_pred_train = model.predict(X_train)
y_pred_test = model.predict(X_test)

# 训练集
train_r2 = r2_score(y_train, y_pred_train)
train_rmse = np.sqrt(mean_squared_error(y_train, y_pred_train))
train_mae = mean_absolute_error(y_train, y_pred_train)
# 测试集
test_r2 = r2_score(y_test, y_pred_test)
test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
test_mae = mean_absolute_error(y_test, y_pred_test)

print(f"\n## {模型名称} 评估")
print(f"训练集 — R²: {train_r2:.4f}  ·  RMSE: {train_rmse:.2f}  ·  MAE: {train_mae:.2f}")
print(f"测试集 — R²: {test_r2:.4f}  ·  RMSE: {test_rmse:.2f}  ·  MAE: {test_mae:.2f}")

# 交叉验证
try:
    cv_scores = cross_val_score(model, X, y, cv=5, scoring="r2")
    print(f"5折 CV R²: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    cv_r2_mean = cv_scores.mean()
    cv_r2_std = cv_scores.std()
except Exception:
    cv_scores = None
    cv_r2_mean = None
    cv_r2_std = None

# %% [markdown]
# ### 特征系数

# %%
if 模型类型 == "poly":
    # 多项式特征，无法直观展示系数
    print("多项式回归：特征系数数量庞大，不逐项列出")
    系数列表 = []
else:
    # 获取线性模型系数
    scaler = model.named_steps["scaler"]
    reg = model.named_steps["reg"]
    coefs = reg.coef_
    系数列表 = []
    for name, coef in sorted(zip(特征列表, coefs), key=lambda x: abs(x[1]), reverse=True):
        direction = "+" if coef > 0 else "-"
        系数列表.append({"特征": name, "系数": round(float(coef), 4), "方向": direction})
        print(f"  {name}: {coef:.4f} ({direction})")

# %% [markdown]
# ### 图表目录

# %%
图表目录 = os.path.join(root_path(), "data", "analysis", "regression", str(数据集ID))
os.makedirs(图表目录, exist_ok=True)

# %% [markdown]
# ### seaborn 预测 vs 实际 + 残差图

# %%
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# 预测 vs 实际
sns.regplot(x=y_test, y=y_pred_test, ax=ax1, scatter_kws={"alpha": 0.4, "s": 15},
            line_kws={"color": "#e53935", "linestyle": "--"})
ax1.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], "k--", alpha=0.3, linewidth=1)
ax1.set_xlabel("实际值"); ax1.set_ylabel("预测值")
ax1.set_title(f"预测 vs 实际  R²={test_r2:.3f}", fontsize=10)

# 残差图
残差 = y_test - y_pred_test
sns.residplot(x=y_pred_test, y=残差, ax=ax2, scatter_kws={"alpha": 0.4, "s": 15},
              line_kws={"color": "#e53935", "linestyle": "--"})
ax2.axhline(0, color="#999", linewidth=0.8, linestyle="-")
ax2.set_xlabel("预测值"); ax2.set_ylabel("残差")
ax2.set_title("残差诊断", fontsize=10)

plt.tight_layout()
回归路径 = os.path.join(图表目录, "regression_diagnostics.png")
fig.savefig(回归路径, dpi=150, bbox_inches="tight")
plt.close(fig)
_图表列表.append(回归路径)
print("回归诊断图已保存")

# %% [markdown]
# ### seaborn 系数柱状图（非多项式模型）

# %%
if 系数列表:
    fig, ax = plt.subplots(figsize=(8, max(4, len(系数列表) * 0.35)))
    系数df = pd.DataFrame(系数列表)
    colors = ["#e53935" if c["方向"] == "+" else "#43a047" for c in 系数列表]
    ax.barh(range(len(系数df)), 系数df["系数"].abs(), color=colors, alpha=0.8)
    ax.set_yticks(range(len(系数df)))
    ax.set_yticklabels(系数df["特征"], fontsize=9)
    ax.axvline(0, color="#333", linewidth=0.8)
    ax.invert_yaxis()
    ax.set_title(f"特征权重 ({模型名称})", fontsize=11)
    for i, (c, coef) in enumerate(zip(colors, 系数df["系数"])):
        ax.text(abs(coef) + 0.01 * max(abs(系数df["系数"])), i, f"{coef:.4f}", va="center", fontsize=8)
    plt.tight_layout()
    系数图路径 = os.path.join(图表目录, "coefficients.png")
    fig.savefig(系数图路径, dpi=120, bbox_inches="tight")
    plt.close(fig)
    _图表列表.append(系数图路径)
    print("系数图已保存")

# %% [markdown]
# ### plotly 交互式预测 vs 实际

# %%
import plotly.graph_objects as go
import plotly.express as px

fig = go.Figure()
fig.add_trace(go.Scatter(x=y_test, y=y_pred_test, mode="markers",
                         marker=dict(size=6, color="#589df6", opacity=0.4),
                         hovertemplate="实际: %{x:.2f}<br>预测: %{y:.2f}<extra></extra>",
                         name="预测点"))
# 完美预测线
min_val, max_val = y_test.min(), y_test.max()
fig.add_trace(go.Scatter(x=[min_val, max_val], y=[min_val, max_val],
                         mode="lines", line=dict(dash="dash", color="#999", width=1),
                         name="完美预测"))
fig.update_layout(height=450, margin=dict(l=50, r=20, t=50, b=50),
                  xaxis_title="实际值", yaxis_title="预测值",
                  title=f"交互式预测 vs 实际  R²={test_r2:.3f}",
                  template="plotly_white")
HTML回归路径 = os.path.join(图表目录, "regression_interactive.html")
fig.write_html(HTML回归路径, include_plotlyjs="cdn", full_html=True,
               config={"displayModeBar": True, "responsive": True})
_HTML列表.append(HTML回归路径)
print("交互式回归图已保存")

# %% [markdown]
# ### plotly 残差分布直方图

# %%
fig = px.histogram(残差, nbins=30, title="残差分布",
                   marginal="box", opacity=0.7,
                   color_discrete_sequence=["#589df6"])
fig.add_vline(x=0, line_dash="dash", line_color="#e53935", annotation_text="0")
fig.update_layout(height=350, template="plotly_white")
HTML残差路径 = os.path.join(图表目录, "residual_hist.html")
fig.write_html(HTML残差路径, include_plotlyjs="cdn", full_html=True,
               config={"displayModeBar": True, "responsive": True})
_HTML列表.append(HTML残差路径)
print("交互式残差图已保存")

# %% [markdown]
# ### plotly 特征重要性（非多项式模型）

# %%
if 系数列表:
    fig = px.bar(pd.DataFrame(系数列表), x="系数", y="特征", orientation="h",
                 title=f"特征重要性 ({模型名称})",
                 color="系数", color_continuous_scale=["#43a047", "#ffffff", "#e53935"],
                 color_continuous_midpoint=0, text="系数")
    fig.update_traces(texttemplate="%{text:.4f}", textposition="outside")
    fig.update_layout(height=max(250, len(系数列表) * 30), margin=dict(l=20, r=60, t=50, b=20),
                      template="plotly_white")
    HTML系数路径 = os.path.join(图表目录, "coefficients_interactive.html")
    fig.write_html(HTML系数路径, include_plotlyjs="cdn", full_html=True,
                   config={"displayModeBar": True, "responsive": True})
    _HTML列表.append(HTML系数路径)
    print("交互式系数图已保存")

# %% [markdown]
# ### 输出标记

# %%
print(f"\n## {模型名称} 摘要")
print(f"特征数: {len(特征列表)}  ·  测试集: {len(X_test)} ({测试比例:.0%})")
print(f"测试 R²: {test_r2:.4f}  ·  RMSE: {test_rmse:.2f}  ·  MAE: {test_mae:.2f}")

if _图表列表:
    print(f"__IMAGES__:{','.join(_图表列表)}")
if _HTML列表:
    print(f"__HTML__:{','.join(_HTML列表)}")

import json as _json
_result = {
    "model": 模型名称, "model_type": 模型类型,
    "features": 特征列表, "target": 目标列名,
    "train": {"r2": round(train_r2, 4), "rmse": round(train_rmse, 2), "mae": round(train_mae, 2)},
    "test": {"r2": round(test_r2, 4), "rmse": round(test_rmse, 2), "mae": round(test_mae, 2)},
    "cv_r2_mean": round(cv_r2_mean, 4) if cv_r2_mean else None,
    "cv_r2_std": round(cv_r2_std, 4) if cv_r2_std else None,
    "coefficients": 系数列表,
}
print(f"__RESULT__:{_json.dumps(_result, ensure_ascii=False)}")
