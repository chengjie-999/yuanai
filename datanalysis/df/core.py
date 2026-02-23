import os.path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from utils.data_path import root_path


def generate_sample_data():
    """生成用于展示的示例数据"""
    # 日期范围
    dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
    n_days = len(dates)

    # 生成数据
    df = pd.DataFrame({
        '日期': dates,
        '销售额': np.random.randint(5000, 20000, size=n_days) + np.linspace(0, 5000, n_days),
        '订单量': np.random.randint(100, 500, size=n_days),
        '客单价': np.round(np.random.uniform(80, 150, size=n_days), 2),
        '地区': np.random.choice(['华东', '华北', '华南', '西南', '西北'], size=n_days)
    })

    # 计算汇总指标
    total_sales = df['销售额'].sum()
    avg_order = df['订单量'].mean()
    avg_price = df['客单价'].mean()
    growth_rate = np.round((df['销售额'].iloc[-1] - df['销售额'].iloc[0]) / df['销售额'].iloc[0] * 100, 2)

    return df, total_sales, avg_order, avg_price, growth_rate


def file_data(file_path):
    df = pd.read_csv(os.path.join(root_path(), f'{file_path}'))
    return df


if __name__ == '__main__':
    df = file_data('data/user/from/sales_old.csv')
    print(df.columns)

