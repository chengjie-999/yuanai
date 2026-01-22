import streamlit as st

import time


def button_with_loading(label, key=None):
    if "loading" not in st.session_state:
        st.session_state.loading = False

    col1, col2 = st.columns([1, 80])  # 控制加载图标宽度
    with col1:
        if st.session_state.loading:
            st.spinner("加载中...")  # 加载动画
    with col2:
        btn = st.button(label, key=key, disabled=st.session_state.loading)

    if btn:
        st.session_state.loading = True
        # 模拟耗时任务（如接口请求、数据处理）
        # time.sleep(2)
        st.session_state.loading = False
        return True
    return False


if __name__ == '__main__':
    # 使用
    if button_with_loading("生成报告"):
        st.success("报告生成完成！")
