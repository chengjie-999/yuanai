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


def va(state):
    open_num = 0
    for k in state:
        if st.session_state[k]:
            open_num += 1
    # print(open_num)
    if not open_num:
        # st.title('欢迎使用数据可视化工具！！！')
        st.info(f'【{open_num}】')
        # 本地图片
        st.image(r'C:\Users\24727\Desktop\Code\my_spider\data\file\img\home.jpg')
    return open_num


# 封装支持分列的侧边栏按钮状态切换逻辑
def render_sidebar_toggle_button(state_key, button_text, run_func=None, reset_home=True, column=None):
    """
    渲染侧边栏的状态切换按钮（支持分列）

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
        if container.button(f'关闭{button_text}', use_container_width=True):
            st.session_state[state_key] = False
            st.rerun()
        if run_func:
            run_func()
    else:
        if container.button(f'开启{button_text}', use_container_width=True):
            st.session_state[state_key] = True
            if reset_home:
                st.session_state.app_home = False
            st.rerun()
