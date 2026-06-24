# %% [markdown]
# # 生物信息学 — 基因表达分布分析
# 直方图 + KDE 核密度曲线，展示 log2_FPKM 基因表达值分布。

# %%
import sys, os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from utils.data_path import root_path

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

__script_name__ = "基因表达分布分析"
__script_desc__ = "对基因表达数据（log2_FPKM）做直方图 + KDE 核密度曲线分析。参数: file_path(可选, CSV文件路径，默认用内置示例数据)"
__script_tags__ = ["生物信息"]

# %% [markdown]
# ### 参数

# %%
文件路径 = sys.argv[1] if len(sys.argv) > 1 else ""

# %% [markdown]
# ### 加载数据

# %%
if 文件路径 and os.path.exists(文件路径):
    df = pd.read_csv(文件路径)
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
df_clean = df.dropna(subset=["log2_FPKM"])
print(f"清洗后: {len(df_clean)} 行")
print(df_clean.head())

# %% [markdown]
# ### 直方图 + KDE

# %%
fig, ax = plt.subplots(figsize=(10, 6))

counts, bins, patches = ax.hist(df_clean["log2_FPKM"], bins=30, alpha=0.7, label="直方图")

log2_data = df_clean["log2_FPKM"].to_numpy()
kde = gaussian_kde(log2_data)
x_range = np.linspace(log2_data.min(), log2_data.max(), 1000)
kde_scaled = kde(x_range) * len(log2_data) * (bins[1] - bins[0])
ax.plot(x_range, kde_scaled, "r-", label="核密度曲线")

ax.set_title("log2_FPKM 分布直方图")
ax.set_xlabel("log2_FPKM")
ax.set_ylabel("频数")
ax.legend()

fig_dir = os.path.join(root_path(), "data", "analysis", "bio")
os.makedirs(fig_dir, exist_ok=True)
bio_png = os.path.join(fig_dir, "log2_FPKM_distribution.png")
fig.savefig(bio_png, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"图表已保存 -> {bio_png}")
print(f"__IMAGES__:{bio_png}")
