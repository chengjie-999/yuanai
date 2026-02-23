import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

# 模拟你的数据（你可以替换为实际读取数据的代码）
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

# 数据清洗（模拟你的清洗步骤）
df_clean = df.dropna(subset=['log2_FPKM'])  # 去除log2_FPKM为空的行
print("数据清洗完成")
print("前5行数据：")
print(df_clean.head())

# 修复绘图部分：将Series转换为numpy数组
plt.figure(figsize=(10, 6))
# 关键修改：使用.values 或 .to_numpy() 转换为numpy数组
sns.histplot(df_clean['log2_FPKM'].values, bins=30, kde=True)
plt.title('log2_FPKM 分布直方图')
plt.xlabel('log2_FPKM')
plt.ylabel('频数')
plt.show()