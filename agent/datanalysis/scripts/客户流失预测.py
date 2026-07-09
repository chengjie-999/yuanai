# %% [markdown]
# # 客户流失预测
# EDA 探索分析 + 逻辑回归建模 + 交叉验证 + ROC 曲线 + 最优阈值。

# %%
import os, sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import roc_auc_score, roc_curve, confusion_matrix, precision_recall_curve
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from utils.data_path import root_path

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

__script_name__ = "客户流失预测"
__script_desc__ = "客户流失预测：EDA+逻辑回归+交叉验证+ROC曲线+最优阈值分析。file_path默认使用内置示例数据，无需用户提供即可直接运行。label_col默认'churn'"
__script_tags__ = ["客户分析", "机器学习"]
__script_params__ = ["file_path", "label_col", "feature_cols", "predict_path"]

_图表列表 = []
_HTML列表 = []

# %% [markdown]
# ### 参数

# %%
文件路径 = sys.argv[1] if len(sys.argv) > 1 else "data/user/sales_old.csv"
标签列   = sys.argv[2] if len(sys.argv) > 2 else "churn"
特征列   = sys.argv[3] if len(sys.argv) > 3 else ""
预测路径 = sys.argv[4] if len(sys.argv) > 4 else ""

# %% [markdown]
# ### 加载 + 清洗

# %%
full_path = os.path.join(root_path(), 文件路径)
if not os.path.exists(full_path):
    raise FileNotFoundError(f"文件不存在: {full_path}")

df = pd.read_csv(full_path)

if 标签列 not in df.columns:
    raise ValueError(f"标签列「{标签列}」不存在。可用列: {list(df.columns)}")

n0 = len(df)
df = df.dropna(subset=[标签列])
df = df.drop_duplicates()
print(f"清洗: {n0} -> {len(df)} 行")

# %% [markdown]
# ### 特征选择

# %%
if 特征列:
    特征列表 = [c.strip() for c in 特征列.split(",")]
    missing = [c for c in 特征列表 if c not in df.columns]
    if missing:
        raise ValueError(f"特征列不存在: {missing}")
else:
    特征列表 = [c for c in df.select_dtypes(include=[np.number]).columns if c != 标签列]
    if len(特征列表) > 10:
        特征列表 = 特征列表[:10]

if len(特征列表) < 2:
    raise ValueError(f"可用特征列不足（需要至少 2 列），当前: {特征列表}")

for c in 特征列表:
    if df[c].isnull().any():
        df[c] = df[c].fillna(df[c].median())

# %% [markdown]
# ### EDA

# %%
流失率 = df[标签列].mean()

相关性 = []
for c in 特征列表:
    相关性.append({"特征": c, "与流失相关系数": round(df[c].corr(df[标签列]), 4)})
相关表 = pd.DataFrame(相关性).sort_values("与流失相关系数", key=abs, ascending=False)
print("特征与流失相关性:")
print(相关表.to_string(index=False))

# %% [markdown]
# ### seaborn 小提琴图 — 流失 vs 非流失特征分布

# %%
fig_dir = os.path.join(root_path(), "data", "analysis", "churn")
os.makedirs(fig_dir, exist_ok=True)

top_features = 相关表.head(4)["特征"].tolist()
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
axes = axes.flatten()

for i, feat in enumerate(top_features):
    sns.violinplot(data=df, x=标签列, y=feat, palette={0: "#43a047", 1: "#e53935"},
                   inner="quartile", ax=axes[i])
    axes[i].set_title(f"{feat} 按流失状态分布", fontsize=10)
    流失均值 = df[df[标签列]==1][feat].mean()
    留存均值 = df[df[标签列]==0][feat].mean()
    axes[i].text(0.5, 0.95, f"留存均值={留存均值:.2f}\n流失均值={流失均值:.2f}",
                 transform=axes[i].transAxes, ha="center", va="top", fontsize=8, color="#666")

plt.tight_layout()
violin_png = os.path.join(fig_dir, "feature_violin.png")
fig.savefig(violin_png, dpi=150, bbox_inches="tight")
plt.close(fig)
_图表列表.append(violin_png)
print("特征小提琴图已保存")

# %% [markdown]
# ### seaborn pairplot — 特征关系探索

# %%
if len(特征列表) >= 2:
    样本数据 = df[特征列表[:6] + [标签列]].sample(min(300, len(df)), random_state=42)
    样本数据[标签列] = 样本数据[标签列].map({0: "留存", 1: "流失"})
    g = sns.pairplot(样本数据, vars=特征列表[:4], hue=标签列,
                     palette={"留存": "#43a047", "流失": "#e53935"},
                     diag_kind="kde", plot_kws={"alpha": 0.4, "s": 12})
    g.fig.suptitle("特征关系探索 (Pairplot)", y=1.01, fontsize=13)
    pairplot_png = os.path.join(fig_dir, "feature_pairplot.png")
    g.fig.savefig(pairplot_png, dpi=120, bbox_inches="tight")
    plt.close("all")
    _图表列表.append(pairplot_png)
    print("特征 Pairplot 已保存")

# %% [markdown]
# ### 建模

# %%
X = df[特征列表].values
y = df[标签列].values

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.3, random_state=42, stratify=y
)

model = LogisticRegression(max_iter=1000, class_weight="balanced")
model.fit(X_train, y_train)
print(f"训练完成，训练集: {len(X_train)}，测试集: {len(X_test)}")

# %% [markdown]
# ### 交叉验证

# %%
cv_scores = cross_val_score(model, X_scaled, y, cv=5, scoring="roc_auc")
print(f"\n5折 CV AUC: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
print(f"  CV folds: {[f'{s:.4f}' for s in cv_scores]}")

# %% [markdown]
# ### 评估

# %%
y_pred = model.predict(X_test)
y_prob = model.predict_proba(X_test)[:, 1]

auc = roc_auc_score(y_test, y_prob)
cm = confusion_matrix(y_test, y_pred)

print(f"\n## 客户流失预测")
print(f"样本数: {len(df)}  ·  流失率: {流失率:.1%}  ·  特征数: {len(特征列表)}")
print(f"特征列: {', '.join(特征列表)}")
print(f"\n### 模型评估")
print(f"AUC: {auc:.4f}")
print(f"训练集准确率: {model.score(X_train, y_train):.2%}")
print(f"测试集准确率: {model.score(X_test, y_test):.2%}")
print(f"混淆矩阵 (测试集):")
print(f"  真负 {cm[0][0]:5d}  |  假正 {cm[0][1]:5d}")
print(f"  假负 {cm[1][0]:5d}  |  真正 {cm[1][1]:5d}")

print(f"\n### 特征权重")
for name, coef in sorted(zip(特征列表, model.coef_[0]), key=lambda x: abs(x[1]), reverse=True):
    direction = "→ 促进流失" if coef > 0 else "← 抑制流失"
    print(f"  {name}: {coef:.4f}  {direction}")

# %% [markdown]
# ### 最优阈值分析 (Youden's Index)

# %%
fpr, tpr, thresholds = roc_curve(y_test, y_prob)
youden_index = tpr - fpr
optimal_idx = np.argmax(youden_index)
optimal_threshold = thresholds[optimal_idx]
optimal_tpr = tpr[optimal_idx]
optimal_fpr = fpr[optimal_idx]

print(f"\n### 最优阈值 (Youden's Index)")
print(f"阈值: {optimal_threshold:.4f}")
print(f"TPR: {optimal_tpr:.4f}  ·  FPR: {optimal_fpr:.4f}  ·  Youden: {youden_index[optimal_idx]:.4f}")

# 按最优阈值重新预测
y_pred_optimal = (y_prob >= optimal_threshold).astype(int)
cm_optimal = confusion_matrix(y_test, y_pred_optimal)
print(f"最优阈值混淆矩阵: TN={cm_optimal[0][0]} FP={cm_optimal[0][1]} FN={cm_optimal[1][0]} TP={cm_optimal[1][1]}")

# %% [markdown]
# ### matplotlib 静态图：混淆矩阵 + 权重 + 流失率饼图

# %%
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=axes[0],
            xticklabels=["未流失", "流失"], yticklabels=["未流失", "流失"])
axes[0].set_title(f"混淆矩阵  AUC={auc:.3f}", fontsize=10)
axes[0].set_xlabel("预测"); axes[0].set_ylabel("实际")

权重df = pd.DataFrame({"特征": 特征列表, "权重": model.coef_[0]})
权重df = 权重df.sort_values("权重", key=abs, ascending=True)
colors = ["#e53935" if w > 0 else "#43a047" for w in 权重df["权重"]]
axes[1].barh(权重df["特征"], 权重df["权重"], color=colors, alpha=0.8)
axes[1].axvline(0, color="#333", linewidth=0.8)
axes[1].set_title("特征权重", fontsize=10)

axes[2].pie([1 - 流失率, 流失率], labels=["留存", "流失"],
            autopct="%1.1f%%", colors=["#43a047", "#e53935"], startangle=90)
axes[2].set_title(f"样本流失率 {流失率:.1%}", fontsize=10)

plt.tight_layout()
churn_png = os.path.join(fig_dir, "churn_analysis.png")
fig.savefig(churn_png, dpi=150, bbox_inches="tight")
plt.close(fig)
_图表列表.append(churn_png)
print(f"图表已保存 -> {churn_png}")

# %% [markdown]
# ### plotly 交互式 ROC 曲线

# %%
import plotly.graph_objects as go

fig = go.Figure()
fig.add_trace(go.Scatter(x=fpr, y=tpr, mode="lines",
                         name=f"ROC (AUC={auc:.4f})",
                         line=dict(color="#589df6", width=2),
                         hovertemplate="FPR: %{x:.3f}<br>TPR: %{y:.3f}<extra></extra>"))
fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines",
                         name="随机猜测", line=dict(dash="dash", color="#999", width=1)))
# 最优阈值点
fig.add_trace(go.Scatter(x=[optimal_fpr], y=[optimal_tpr], mode="markers",
                         name=f"最优阈值 ({optimal_threshold:.2f})",
                         marker=dict(color="#e53935", size=10, symbol="star"),
                         hovertemplate=f"阈值: {optimal_threshold:.3f}<br>TPR: {optimal_tpr:.3f}<br>FPR: {optimal_fpr:.3f}<extra></extra>"))
fig.update_layout(height=400, margin=dict(l=50, r=20, t=30, b=50),
                  xaxis_title="假阳性率 (FPR)", yaxis_title="真阳性率 (TPR)",
                  template="plotly_white")
html_roc_path = os.path.join(fig_dir, "roc_interactive.html")
fig.write_html(html_roc_path, include_plotlyjs="cdn", full_html=True,
               config={"displayModeBar": True, "responsive": True})
_HTML列表.append(html_roc_path)
print("交互式 ROC 曲线已保存")

# %% [markdown]
# ### plotly 交互式特征重要性

# %%
import plotly.express as px

权重df2 = pd.DataFrame({"特征": 特征列表, "系数": model.coef_[0], "abs": np.abs(model.coef_[0])})
权重df2 = 权重df2.sort_values("abs", ascending=True)
权重df2["方向"] = 权重df2["系数"].apply(lambda x: "促进流失" if x > 0 else "抑制流失")

fig = px.bar(权重df2, x="abs", y="特征", orientation="h",
             color="方向", color_discrete_map={"促进流失": "#e53935", "抑制流失": "#43a047"},
             title=f"特征重要性 (AUC={auc:.4f}, CV={cv_scores.mean():.4f}±{cv_scores.std():.4f})",
             text=权重df2["系数"].round(4))
fig.update_traces(textposition="outside")
fig.update_layout(height=max(250, len(特征列表) * 30), margin=dict(l=20, r=60, t=50, b=20),
                  template="plotly_white")
html_imp_path = os.path.join(fig_dir, "feature_importance_interactive.html")
fig.write_html(html_imp_path, include_plotlyjs="cdn", full_html=True,
               config={"displayModeBar": True, "responsive": True})
_HTML列表.append(html_imp_path)
print("交互式特征重要性已保存")

# %% [markdown]
# ### 预测新客（可选）

# %%
if 预测路径:
    pred_full = os.path.join(root_path(), 预测路径)
    if os.path.exists(pred_full):
        new_df = pd.read_csv(pred_full)
        new_X = new_df[特征列表].fillna(0).values
        new_pred_prob = model.predict_proba(scaler.transform(new_X))[:, 1]
        new_pred = (new_pred_prob >= optimal_threshold).astype(int)
        预测流失 = new_pred.sum()
        print(f"\n### 新客预测 ({预测路径})")
        print(f"总数: {len(new_df)}  ·  预测流失: {预测流失}  ·  流失率: {预测流失/len(new_df):.1%}")
        print(f"阈值: {optimal_threshold:.4f}")

# %% [markdown]
# ### 输出标记

# %%
if _图表列表:
    print(f"__IMAGES__:{','.join(_图表列表)}")
if _HTML列表:
    print(f"__HTML__:{','.join(_HTML列表)}")

import json as _json
_result = {
    "sample_size": len(df), "churn_rate": round(float(流失率), 4),
    "features": 特征列表, "n_features": len(特征列表),
    "auc": round(auc, 4), "cv_auc_mean": round(cv_scores.mean(), 4), "cv_auc_std": round(cv_scores.std(), 4),
    "train_acc": round(float(model.score(X_train, y_train)), 4),
    "test_acc": round(float(model.score(X_test, y_test)), 4),
    "confusion_matrix": {"TN": int(cm[0][0]), "FP": int(cm[0][1]), "FN": int(cm[1][0]), "TP": int(cm[1][1])},
    "optimal_threshold": round(float(optimal_threshold), 4),
    "coefficients": [{"feature": name, "coef": round(float(c), 4)} for name, c in zip(特征列表, model.coef_[0])],
}
print(f"__RESULT__:{_json.dumps(_result, ensure_ascii=False)}")
