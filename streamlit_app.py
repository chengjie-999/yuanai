import streamlit as st
from spider_lx.ui import selenium_ui

# =================================== #
# 运行：streamlit run streamlit_app.py #
# =================================== #

if "crawl_result" not in st.session_state:
    st.session_state.crawl_result = []  # 保存爬取结果

# ======================
# 第二步：设置页面基础样式
# ======================
st.set_page_config(page_title="自动化爬虫可视化工具", page_icon="🕷️")
st.title("🕷️ 自动化爬虫项目 - Streamlit 可视化版")
st.divider()
# web自动化
selenium_ui.app_main()

