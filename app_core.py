import streamlit as st


def initializing_state(init_state):
    """
    初始化selenium_ui的会话状态（跨步骤保存数据）
    :return:
    """
    for key, default_val in init_state.items():
        if key not in st.session_state:
            st.session_state[key] = default_val


def reset_to_initial(init_state):
    """回归初始化状态：用保留的初始模板重置所有状态"""
    for key, default_val in init_state.items():
        st.session_state[key] = default_val  # 强制覆盖为初始值
