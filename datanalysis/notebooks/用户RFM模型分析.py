#!/usr/bin/env python
# coding: utf-8

# In[4]:


import os

import numpy as np
import pandas as pd 
from pyecharts.charts import *
from pyecharts import options as opts
import seaborn as sns


# In[2]:


from pyecharts.globals import CurrentConfig, OnlineHostType
CurrentConfig.ONLINE_HOST = OnlineHostType.NOTEBOOK_HOST


# In[5]:


from utils.data_path import root_path

df = pd.read_excel(os.path.join(root_path(), 'data/user/from/订单明细.xlsx'))
df.head()


# In[4]:


df.info()


# In[5]:


df['交易状态'].unique()


# In[6]:


df = df.loc[df['交易状态'] == '交易成功']


# In[7]:


df = df[['用户编号', '交易时间', '金额']]


# In[8]:


df.head(10)


# # R(近期交易时间)

# - 最近一次交易时间距离统计日期的天数

# In[9]:


start_data = df['交易时间'].max()
start_data


# In[10]:


# 求每个用户最后一次交易时间
r = df.groupby('用户编号')['交易时间'].max().reset_index()
r.head()


# In[11]:


r['R'] = (start_data-r['交易时间']).dt.days
r = r[['用户编号', 'R']]
r.head()


# # F(交易频次)

# - 当天多次交易仅计算一次

# In[12]:


# 以用户编号分组对交易时间去重计数
# df.groupby('用户编号').agg(F=('交易日期', 'nunique')).reset_index()
f = df.groupby('用户编号', as_index=False).agg(F=('交易时间', 'nunique'))
f.head(10)


# # M(交易金额)

# In[13]:


m = df.groupby('用户编号', as_index=False).agg(M=('金额', 'sum'))
m.head()


# # RFM合并

# In[14]:


# merge(左右内外交叉)\join(左右内外)\concat(内外)
rfm = r.merge(f, on='用户编号').merge(m, on='用户编号')
rfm.head()
# pd.merge(r, f, on='用户编号')


# # RFM均值

# In[15]:


# 越接近零越对称
rfm['R'].skew()
# -0.23497860252734598
sns.kdeplot(x=rfm['R'])


# In[16]:


rfm['F'].skew()
# 4.623659633018703
sns.kdeplot(x=rfm['F'])


# In[17]:


rfm['M'].skew()
# 14.15870871182295
sns.kdeplot(x=rfm['M'])


# In[18]:


rfm.describe().round(2)


# In[19]:


# R指标的均值
AVG_R = rfm['R'].mean()
# F指标的均值
AVG_F = rfm['F'].mean()
# M指标的均值
AVG_M = rfm['M'].mean()


# In[20]:


# 100\10\1用于分类
rfm['R_score'] = (rfm['R'] < AVG_R)*100
rfm['F_score'] = (rfm['F'] > AVG_F)*10
rfm['M_score'] = (rfm['M'] > AVG_M)*1


# In[21]:


# 总分值
rfm['Total_score'] = rfm['R_score']+rfm['F_score']+rfm['M_score']
rfm.head()


# # 标签映射

# In[22]:


rfm['Total_score'].unique()


# In[23]:


dct = {111: '重要价值',
       110: '一般价值',
       101: '重要发展',
       100: '一般发展',
       11: '重要保持',
       10: '一般保持',
       1: '重要挽留',
       0: '一般挽留'}


# In[24]:


rfm['用户标签'] = rfm['Total_score'].map(dct)


# In[25]:


rfm['用户标签'].unique()


# In[26]:


rfm.head()


# # 各类用户占比

# In[34]:


cnt = rfm['用户标签'].value_counts().reset_index()
cnt


# In[35]:


# 各类用户的人数统计
cnt = rfm['用户标签'].value_counts().reset_index()
cnt.columns = ['用户标签', '人数']
cnt['人数占比'] = cnt['人数'] / cnt['人数'].sum()
cnt


# In[36]:


# 各类用户的金额统计
amt = rfm.groupby('用户标签', as_index=False)['M'].sum()
amt.columns = ['用户标签', '金额']
amt['金额占比'] = amt['金额'] / amt['金额'].sum()
amt


# In[37]:


tb = pd.merge(cnt, amt, on='用户标签')
tb['人数占比'] = tb['人数占比'].apply(lambda x: '{:.2%}'.format(x))
tb['金额占比'] = tb['金额占比'].apply(lambda x: '{:.2%}'.format(x))
tb.sort_values(by=['金额', '人数'], ascending=[False, False], inplace=True)
tb


# In[43]:


del tb['金额占比']
tb


# # 可视化

# In[49]:


pie = Pie(init_opts=opts.InitOpts(width='1100px', height='500px'))
pie.add(
    '交易金额',
    tb[['用户标签', '金额']].values.tolist(),
    radius=['20%', '70%'],
    # 第一项为宽度,第二项为高度
    center=['25%', '50%'],
    rosetype='radius'
)
pie.set_series_opts(label_opts=opts.LabelOpts(formatter='{b}{d}%'))
pie.add(
    '交易人数',
    tb[['用户标签', '人数']].values.tolist(),
    radius=['20%', '70%'],
    # 第一项为宽度,第二项为高度
    center=['75%', '50%'],
    rosetype='radius'
)
pie.render('RFM模型分析.html')
pie.render_notebook()


# In[45]:


# 各区域的RFM模型分析
user = pd.read_excel('data/用户信息.xlsx')
user.head()


# In[51]:


rfm_user = rfm.merge(user, on='用户编号')[['用户编号', '用户标签', '区域', 'M']]
rfm_user.head()


# In[55]:


# 各区域内各类用户的人数和金额统计
tb2 = rfm_user.groupby(['区域', '用户标签']).agg(人数=('用户编号', 'count'), 金额=('M', 'sum')).reset_index()
tb2.sort_values(['金额','人数'], ascending = [False, False], inplace = True)
tb2.head()


# In[56]:


# 选项卡多图, 每个区域一个图表
tab = Tab()
for i in tb2['区域'].unique():
    # print(i)
    data = tb2[tb2['区域'] == i]
    pie = Pie(init_opts=opts.InitOpts(width='1100px', height='500px'))
    pie.add(
        '交易金额',
        data[['用户标签', '金额']].values.tolist(),
        radius=['20%', '70%'],
        # 第一项为宽度,第二项为高度
        center=['25%', '50%'],
        rosetype='radius'
    )
    pie.add(
        '交易人数',
        data[['用户标签', '人数']].values.tolist(),
        radius=['20%', '70%'],
        # 第一项为宽度,第二项为高度
        center=['75%', '50%'],
        rosetype='radius'
    )
    pie.set_series_opts(label_opts=opts.LabelOpts(formatter='{b}{d}%'))
    tab.add(pie, i)
tab.render('RFM模型分析-区域.html')
tab.render_notebook()


# In[ ]:




