import os.path

import streamlit as st
import pandas as pd

import aicode.headui
from spiderlx.ui import spider_app
from datanalysis.ui import core

from utils.app_core import *
from utils.data_path import root_path


# 运行：streamlit run streamlit_app.py

# # 基础用法：禁用自动打开浏览器
# streamlit run streamlit_app.py --server.headless true
# # 进阶：同时关闭使用统计（避免额外弹窗/请求）
# streamlit run streamlit_app.py --server.headless true --browser.gatherUsageStats false
# =================================== #
# --------------------------
# 1. 页面基础配置 (必须放在最前面)
# --------------------------
st.set_page_config(
    page_title="数据可视化 DatAnalysis",
    page_icon=os.path.join(root_path(), 'data/file/img/home.jpg'),
    layout="wide",  # 宽屏布局
    initial_sidebar_state="expanded"  # 侧边栏默认展开
)
# 加载自定义CSS（主脚本已完成set_page_config，此处执行无冲突）
core.local_css()

INITIAL_STATE = {
    "app_home": False,
    "session_show": False,
    "spider": False,
    "test": False,
    'datanalysis': True,
}  # 初始状态

# ======================
# 第一步：初始化会话状态
# ======================
initializing_state(INITIAL_STATE)

# ======================
# 第二步：设置页面基础样式
# ======================

if st.sidebar.button('重载', use_container_width=True):
    st.rerun()
va(INITIAL_STATE)

# 创建侧边栏三列布局（等分），也可自定义比例如 [1,1,1] 或 [2,1,1]
col1, col2, col3 = st.sidebar.columns(3)

# 使用封装的函数，指定每个按钮所在的列
render_sidebar_toggle_button("spider", "爬虫", spider_app.main, column=col1)
render_sidebar_toggle_button("datanalysis", "数据分析", core.main, column=col2)
render_sidebar_toggle_button("test", "ai代码测试", aicode.headui.main, column=col3)

if st.sidebar.button('查看当前session状态'):
    st.write('📌【当前session状态】')
    session_table = [[key, value] for key, value in st.session_state.items()]
    df = pd.DataFrame(session_table, columns=["Session State 键", "对应值"])
    st.dataframe(df, use_container_width=True)

# if st.sidebar.button('播放视频'):
#     online_video_url = "https://www.w3school.com.cn/i/movie.mp4"  # 推荐：短片段，加载快
#     # 直接用st.video()即可，音量键正常、有声音
#     st.video(online_video_url)
