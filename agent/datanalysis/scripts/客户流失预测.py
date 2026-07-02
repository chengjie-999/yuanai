# %% [markdown]
# # 客户流失预测
# EDA 探索分析 + 逻辑回归建模 + 模型评估 + 新客预测。

# %%
import os, sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, confusion_matrix
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from utils.data_path import root_path

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

__script_name__ = "客户流失预测"
__script_desc__ = "客户流失预测：EDA+逻辑回归建模+评估。file_path默认使用内置示例数据，无需用户提供即可直接运行。label_col默认'churn'"
__script_tags__ = ["客户分析"]
__script_params__ = ["file_path", "label_col", "feature_cols", "predict_path"]

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
    direction = "-> 促进流失" if coef > 0 else "<- 抑制流失"
    print(f"  {name}: {coef:.4f}  {direction}")

# %% [markdown]
# ### 可视化

# %%
fig_dir = os.path.join(root_path(), "data", "analysis", "churn")
os.makedirs(fig_dir, exist_ok=True)

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
print(f"图表已保存 -> {churn_png}")
print(f"__IMAGES__:{churn_png}")

# %% [markdown]
# ### 预测新客（可选）

# %%
if 预测路径:
    pred_full = os.path.join(root_path(), 预测路径)
    if os.path.exists(pred_full):
        new_df = pd.read_csv(pred_full)
        new_X = new_df[特征列表].fillna(0).values
        new_pred = model.predict(scaler.transform(new_X))
        预测流失 = new_pred.sum()
        print(f"\n### 新客预测 ({预测路径})")
        print(f"总数: {len(new_df)}  ·  预测流失: {预测流失}  ·  流失率: {预测流失/len(new_df):.1%}")
