import os
import streamlit as st

from spiderlx.ui import playwright
from spiderlx.ui.call_my_api import call_spider_api
from spiderlx.ui.selenium import uiselenium
from webui.app_core import initializing_state, render_toggle_button
from utils.data_path import root_path


INITIAL_STATE = {
    "spider": True,
    "selenium": True,
    "playwright": False,
    "s_step": 1,
    "s_test": False,
    "url": "",
    "api_result": None,
}  # 初始状态


def main():
    initializing_state(INITIAL_STATE)

    col1, col2 = st.columns([3, 1])
    with col1:
        col11, col12 = st.columns(2)
        render_toggle_button("selenium", "selenium", uiselenium.app_main, column=col11)
        render_toggle_button("playwright", "playwright", playwright.main, column=col12)
    with col2:
        container = st.container(border=True)
        container.image(os.path.join(root_path(), 'data/file/img/home.jpg'))
        container.info(f'当前url：{st.session_state.url}')
        if st.session_state.s_step == 1:
            st.session_state.url = container.text_input("请输入要获取数据的URL：", value=f"{st.session_state.url}")
            
            col_api, col_direct = container.columns(2)
            with col_api:
                if container.button('🔌 API请求', use_container_width=True):
                    if st.session_state.url:
                        with container.spinner('正在请求API...'):
                            result = call_spider_api(st.session_state.url, 'text')
                            st.session_state.api_result = result
                    else:
                        container.error('请输入URL')
            
            with col_direct:
                if container.button(f'📥 直接获取', use_container_width=True):
                    pass

        if st.session_state.get('api_result'):
            result = st.session_state.api_result
            if result.get('status') == 'success':
                st.success(f"✅ API请求成功")
                with st.expander("查看返回数据"):
                    data = result.get('data', '')
                    if len(data) > 1000:
                        st.text(data[:1000] + "...")
                    else:
                        st.text(data)
            else:
                st.error(f"❌ API请求失败: {result.get('detail', '未知错误')}")


if __name__ == '__main__':
    st.set_page_config(
        page_title="数据采集",
        page_icon=os.path.join(root_path(), 'data/file/img/home.jpg'),
        layout="wide",  # 宽屏布局
        initial_sidebar_state="expanded"  # 侧边栏默认展开
    )
