#!/usr/bin/env python
# coding: utf-8

# In[1]:


print(1)


# In[2]:


print(1+1)


# In[4]:


import numpy as np
from datetime import datetime, timedelta
import pandas as pd

dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
n_days = len(dates)

# 生成数据
data = pd.DataFrame({
        '日期': dates,
        '销售额': np.random.randint(5000, 20000, size=n_days) + np.linspace(0, 5000, n_days),
        '订单量': np.random.randint(100, 500, size=n_days),
        '客单价': np.round(np.random.uniform(80, 150, size=n_days), 2),
        '地区': np.random.choice(['华东', '华北', '华南', '西南', '西北'], size=n_days)
    })
