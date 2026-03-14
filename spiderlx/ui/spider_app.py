import os

import streamlit as st

from spiderlx.ui import uiselenium, playwright
from utils import initializing_state, render_toggle_button
from utils.data_path import root_path

INITIAL_STATE = {
    "spider": True,
    "selenium": True,
    "playwright": False,
    "s_step": 1,
    "s_test": False,
    "url": "",
}  # 初始状态


def main():
    initializing_state(INITIAL_STATE)
    st.info(f'当前url：{st.session_state.url}')
    if st.session_state.s_step == 1:
        col1, col2 = st.columns([3, 1])
        col1.text_input("请输入要获取数据的URL：", value="https://www.baidu.com")
        if col2.button('开始爬取'):
            pass
    col1, col2 = st.columns(2)
    render_toggle_button("selenium", "selenium", uiselenium.app_main, column=col1)
    render_toggle_button("playwright", "playwright", playwright.main, column=col2)


if __name__ == '__main__':
    st.set_page_config(
        page_title="数据采集",
        page_icon=os.path.join(root_path(), 'data/file/img/home.jpg'),
        layout="wide",  # 宽屏布局
        initial_sidebar_state="expanded"  # 侧边栏默认展开
    )
