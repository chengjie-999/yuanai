import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from utils.data_path import root_path


def generate_sample_data():
    """生成用于展示的示例销售数据（30天 × 4列 + 分类维度）"""
    dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
    n_days = len(dates)

    df = pd.DataFrame({
        '日期': dates,
        '销售额': np.random.randint(5000, 20000, size=n_days) + np.linspace(0, 5000, n_days),
        '订单量': np.random.randint(100, 500, size=n_days),
        '客单价': np.round(np.random.uniform(80, 150, size=n_days), 2),
        '地区': np.random.choice(['华东', '华北', '华南', '西南', '西北'], size=n_days),
    })

    total_sales = df['销售额'].sum()
    avg_order = df['订单量'].mean()
    avg_price = df['客单价'].mean()
    growth_rate = np.round((df['销售额'].iloc[-1] - df['销售额'].iloc[0]) / df['销售额'].iloc[0] * 100, 2)

    return df, total_sales, avg_order, avg_price, growth_rate


def load_file(path: str) -> pd.DataFrame:
    """加载本地数据文件，自动识别 CSV / Excel / JSON"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(path)
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    elif ext == ".json":
        return pd.read_json(path)
    raise ValueError(f"不支持的文件类型: {ext}")


def data_dir(subdir: str = "") -> str:
    """返回 data/ 目录的绝对路径，方便 notebook 中拼接文件路径"""
    p = os.path.join(root_path(), "data", subdir)
    os.makedirs(p, exist_ok=True)
    return p

