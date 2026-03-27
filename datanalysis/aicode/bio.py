import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import gaussian_kde  # 导入核密度计算库


def main():
    # ========== 关键添加：配置matplotlib支持中文 ==========
    plt.rcParams['font.sans-serif'] = ['SimHei']  # 用黑体显示中文
    plt.rcParams['axes.unicode_minus'] = False  # 正常显示负号

    # 模拟数据
    data = {
        'Gene': ['Gene_1', 'Gene_2', 'Gene_3', 'Gene_4', 'Gene_5'],
        'Chromosome': ['Chr7', 'Chr20', 'Chr15', 'Chr11', 'Chr8'],
        'FPKM': [14.404353, 1.786426, 2.601230, 7.630435, 19.579397],
        'Count': [50, 57, 42, 61, 51],
        'P_Value': [0.690000, 0.690097, 0.930607, 0.497312, 0.230251],
        'DEG': ['Not Significant'] * 5,
        'log2_FPKM': [3.945266, 1.478416, 1.848490, 3.109433, 4.363129]
    }
    df = pd.DataFrame(data)

    # 数据清洗
    df_clean = df.dropna(subset=['log2_FPKM'])
    print("数据清洗完成")
    print("前5行数据：")
    print(df_clean.head())

    # 绘制直方图+手动KDE曲线
    plt.figure(figsize=(10, 6))

    # 1. 绘制直方图
    counts, bins, patches = plt.hist(df_clean['log2_FPKM'], bins=30, alpha=0.7, label='直方图')

    # 2. 手动计算并绘制核密度曲线（KDE）
    log2_fpkm_data = df_clean['log2_FPKM'].to_numpy()
    kde = gaussian_kde(log2_fpkm_data)  # 计算核密度
    x_range = np.linspace(min(log2_fpkm_data), max(log2_fpkm_data), 1000)  # 生成x轴范围
    # 缩放KDE曲线到直方图的刻度（匹配频数）
    kde_scaled = kde(x_range) * len(log2_fpkm_data) * (bins[1] - bins[0])
    plt.plot(x_range, kde_scaled, 'r-', label='核密度曲线')

    # 图表美化
    plt.title('log2_FPKM 分布直方图')
    plt.xlabel('log2_FPKM')
    plt.ylabel('频数')
    plt.legend()
    plt.show()


if __name__ == '__main__':
    main()
