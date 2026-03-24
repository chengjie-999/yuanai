import os.path
import time

import streamlit as st
import pandas as pd

# 导入功能模块（保持原有导入路径）
from aicode import headui
from spiderlx.ui import spider_app
from datanalysis.ui import core
from yuanai.ui import ai

from utils.app_core import initializing_state, render_toggle_button
from utils.data_path import root_path

# ==============================
# 页面基础配置 (必须放在最前面)
# streamlit run streamlit_app.py
# ==============================
st.set_page_config(
    page_title="数据可视化 DatAnalysis",
    page_icon=os.path.join(root_path(), 'data/file/img/home.jpg'),
    layout="wide",  # 宽屏布局
    initial_sidebar_state="expanded"  # 侧边栏默认展开
)

# 加载自定义CSS
core.local_css()

# ==============================
# 常量定义（提升代码可维护性）
# ==============================
# 功能配置：键名、标签显示名称、对应的功能入口函数
FEATURE_CONFIG = {
    "spider": {"tab_name": "🕷 爬虫", "func": spider_app.main},
    "datanalysis": {"tab_name": "📊 数据分析", "func": core.main},
    "test": {"tab_name": "💻 AI代码测试", "func": headui.main},
}

# 初始状态配置（基础标签+功能开关）
INITIAL_STATE = {
    "app_home": False,
    "session_show": False,
    "auto_refresh": False,
    "spider": True,
    "test": False,
    "datanalysis": False,  # 数据分析默认开启
}

# ==============================
# 初始化会话状态
# ==============================
initializing_state(INITIAL_STATE)

# ==============================
# 自定义CSS样式（优化标签页显示）
# ==============================
st.markdown("""
    <style>
    /* 调整标签页整体样式 */
    div[data-baseweb="tab-list"] {
        gap: 0.5rem;  /* 标签之间的间距 */
        padding: 1rem 0;  /* 上下内边距 */
    }
    /* 调整标签按钮样式 */
    button[data-baseweb="tab"] {
        font-size: 1.2rem !important;  /* 字体大小（放大） */
        padding: 1rem 2rem !important;  /* 内边距（按钮更大） */
        border-radius: 8px !important;  /* 圆角更柔和 */
        font-weight: 600 !important;  /* 字体加粗 */
    }
    /* 选中标签的样式 */
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #1f77b4 !important;  /* 选中标签的背景色 */
        color: white !important;
    }
    /* 开关按钮容器样式 */
    .stToggleButton {
        padding: 0.5rem;
    }
    </style>
    """, unsafe_allow_html=True)

# ==============================
# 侧边栏功能按钮
# ==============================
with st.sidebar:
    col1, col2 = st.columns(2)
    if col1.button('重载', use_container_width=True):
        st.rerun()
    render_toggle_button("auto_refresh", '自动刷新', column=col2)

# ==============================
# 第一步：构建动态标签页列表（核心修改：设置标签永远在最后）
# ==============================
# 固定基础标签：首页（单独拆分，设置标签放到最后）
home_tab = [("🏠 首页", "home")]

# 动态标签（根据功能开关状态生成）
dynamic_tabs = []
for feature_key, config in FEATURE_CONFIG.items():
    if st.session_state.get(feature_key):
        dynamic_tabs.append((config["tab_name"], feature_key))

# 系统设置标签（固定放在最后）
settings_tab = [("⚙ 系统设置", "settings")]

# 合并标签列表：首页 → 开启的功能标签 → 系统设置（确保设置在最后）
all_tabs = home_tab + dynamic_tabs + settings_tab

# 提取标签显示名称（用于创建st.tabs）
tab_labels = [tab[0] for tab in all_tabs]
# 创建标签页对象
tabs = st.tabs(tab_labels)

# ==============================
# 第二步：绑定标签页内容
# ==============================
# 遍历所有标签，绑定对应的内容
for idx, (tab_label, tab_key) in enumerate(all_tabs):
    with tabs[idx]:
        # 1. 首页标签内容
        if tab_key == "home":
            st.write("欢迎使用数据可视化平台！")
            ai.main()
            # 查看Session状态按钮
            if st.button('查看当前session状态', use_container_width=True):
                st.write('📌【当前session状态】')
                session_table = [[key, value] for key, value in st.session_state.items()]
                df = pd.DataFrame(session_table, columns=["Session State 键", "对应值"])
                st.dataframe(df, use_container_width=True)
            st.write("---")
            st.subheader("已开启的功能")
            # 显示当前开启的功能列表
            enabled_features = [FEATURE_CONFIG[k]["tab_name"] for k in FEATURE_CONFIG if st.session_state.get(k)]
            if enabled_features:
                for feat in enabled_features:
                    st.success(f"✅ {feat}")
            else:
                st.info("暂无开启的功能，请前往「系统设置」开启功能")

        # 2. 系统设置标签内容（集中管理功能开关）
        elif tab_key == "settings":
            st.info("开启功能会自动添加对应标签页（显示在首页和设置之间），关闭则移除")

            # 分三列展示功能开关按钮
            col1, col2, col3 = st.columns(3)

            # 爬虫功能开关
            render_toggle_button(
                state_key="spider",
                button_text="爬虫功能",
                column=col1
            )

            # 数据分析功能开关
            render_toggle_button(
                state_key="datanalysis",
                button_text="数据分析功能",
                column=col2
            )

            # AI代码测试功能开关
            render_toggle_button(
                state_key="test",
                button_text="AI代码测试功能",
                column=col3
            )

        # 3. 动态功能标签内容
        elif tab_key in FEATURE_CONFIG:

            # 执行功能核心逻辑（增加异常捕获）
            try:
                FEATURE_CONFIG[tab_key]["func"]()
            except Exception as e:
                st.error(f"功能加载失败：{str(e)}")
                st.warning("请检查功能模块是否正常，或联系开发者排查问题")


# ==============================
# 额外功能（可选）
# ==============================
# if st.sidebar.button('播放视频'):
#     online_video_url = "https://www.w3school.com.cn/i/movie.mp4"
#     st.video(online_video_url)
if st.session_state.auto_refresh:
    time.sleep(20)
    st.rerun()
