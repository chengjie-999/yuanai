import streamlit as st
from spider_lx.ui import selenium_ui

# =================================== #
# 运行：streamlit run streamlit_app.py
# # 基础用法：禁用自动打开浏览器
# streamlit run streamlit_app.py --server.headless true
#
# # 进阶：同时关闭使用统计（避免额外弹窗/请求）
# streamlit run streamlit_app.py --server.headless true --browser.gatherUsageStats false
# =================================== #

if "crawl_result" not in st.session_state:
    st.session_state.crawl_result = None  # 保存爬取结果

# ======================
# 第二步：设置页面基础样式
# ======================
st.set_page_config(page_title="自动化爬虫可视化工具", page_icon="🕷️")
st.sidebar.title("🕷️ 自动化爬虫")
# web自动化
selenium_ui.app_main()

