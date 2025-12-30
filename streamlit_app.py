import streamlit as st
import time
from spider_lx.auto.web.selenium import selenium_cj


# ======================
# 第一步：初始化会话状态（跨步骤保存数据）
# ======================
if "web_driver" not in st.session_state:
    st.session_state.web_driver = ''  # 已完成自动化的网站

if "browser_started" not in st.session_state:
    st.session_state.browser_started = False  # 标记浏览器是否已启动

if "web_code" not in st.session_state:
    st.session_state.web_code = 0  # 已完成自动化的网站
if "web_name" not in st.session_state:
    st.session_state.web_name = ''  # 已完成自动化的网站
if "step" not in st.session_state:
    st.session_state.step = 1  # 1:输入参数 2:执行爬取 3:完成
if "url" not in st.session_state:
    st.session_state.url = ""  # 保存用户输入的URL
if "crawl_result" not in st.session_state:
    st.session_state.crawl_result = []  # 保存爬取结果

# ======================
# 第二步：设置页面基础样式
# ======================
st.set_page_config(page_title="自动化爬虫可视化工具", page_icon="🕷️")
st.title("🕷️ 自动化爬虫项目 - Streamlit 可视化版")
st.divider()
selenium_cj.app_main()

