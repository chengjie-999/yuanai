import streamlit as st
import pandas as pd
from spiderlx.ui import uiselenium, ai
from spiderlx.core.save import save_data
from app_core import initializing_state

# 运行：streamlit run streamlit_app.py
# # 基础用法：禁用自动打开浏览器
# streamlit run streamlit_app.py --server.headless true
#
# # 进阶：同时关闭使用统计（避免额外弹窗/请求）
# streamlit run streamlit_app.py --server.headless true --browser.gatherUsageStats false
# =================================== #
INITIAL_STATE = {
    "app_home": True,
    "session_show": False,
    "selenium": True,
    "test": False,
}  # 初始状态

# ======================
# 第一步：初始化会话状态
# ======================
initializing_state(INITIAL_STATE)

# ======================
# 第二步：设置页面基础样式
# ======================
st.set_page_config(page_title="可视化工具", page_icon="🕷️")
if st.session_state.app_home:
    # st.title('欢迎使用数据可视化工具！！！')
    # 本地图片
    st.image(r'C:\Users\24727\Desktop\Code\my_spider\data\file\img\home.png')
if st.session_state.selenium:
    # web自动化
    uiselenium.app_main()

if st.session_state.test:
    ai.test.main()
    if st.sidebar.button('关闭ai代码测试'):
        st.session_state.app_home = True
        st.session_state.test = False
        st.rerun()
else:
    if st.sidebar.button('ai代码测试'):
        st.session_state.app_home = False
        st.session_state.test = True
        st.rerun()

if st.sidebar.button('查看当前session状态'):
    st.write('📌【当前session状态】')
    session_table = [[key, value] for key, value in st.session_state.items()]
    df = pd.DataFrame(session_table, columns=["Session State 键", "对应值"])
    st.dataframe(df, use_container_width=True)

# if st.sidebar.button('播放视频'):
#     online_video_url = "https://www.w3school.com.cn/i/movie.mp4"  # 推荐：短片段，加载快
#     # 直接用st.video()即可，音量键正常、有声音
#     st.video(online_video_url)

