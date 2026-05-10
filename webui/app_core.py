import os
import time

import pandas as pd
import streamlit as st

from utils.data_path import root_path


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


def va(state):
    """计算当前功能状态的开启数量，并根据数量显示不同的界面内容"""
    open_num = 0
    for k in state:
        if st.session_state[k]:
            open_num += 1
    if not open_num:
        st.info(f'【{open_num}】')
        home_img = os.path.join(root_path(), 'data', 'file', 'img', 'home.jpg')
        if os.path.exists(home_img):
            st.image(home_img)
    return open_num


# 封装支持分列的侧边栏按钮状态切换逻辑
def render_toggle_button(state_key, button_text, run_func=None, reset_home=True, column=None):
    """
    渲染状态切换按钮（支持分列）

    参数:
    - state_key: session_state中的状态键名
    - button_text: 按钮文本（关闭/开启功能）
    - run_func: 状态为True时要执行的函数（可选）
    - reset_home: 开启功能时是否重置app_home为False（默认True）
    - column: 按钮要放入的列容器（None则直接放在侧边栏根容器）
    """
    # 确定按钮的父容器（列容器 or 侧边栏根容器）
    container = column if column is not None else st.sidebar

    if st.session_state[state_key]:
        if container.button(f'关闭{button_text}', width="stretch"):
            st.session_state[state_key] = False
            st.rerun()
        if run_func:
            run_func()
    else:
        if container.button(f'开启{button_text}', type='primary', width="stretch"):
            st.session_state[state_key] = True
            if reset_home:
                st.session_state.app_home = False
            st.rerun()
    return button_text


def session_df():
    """将当前session状态转换为DataFrame格式，便于展示和存储"""
    session_table = [[key, value] for key, value in st.session_state.items()]
    df = pd.DataFrame(session_table, columns=["key", "value"])
    return df

