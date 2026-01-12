import streamlit as st
from spider_lx.parse_data.xiao_yuan import XiaoYuan


def main():
    st.divider()

    if "xiao_yuan_card_name" not in st.session_state:
        st.session_state.xiao_yuan_card = ''  #

    if "xiao_yuan_card" not in st.session_state:
        st.session_state.xiao_yuan_card = ''  #

    if "xiao_yuan_step" not in st.session_state:
        st.session_state.xiao_yuan_step = 1  # 小猿操作步骤

    xiao_yuan = XiaoYuan(st.session_state.web_driver)
    col1, col2 = st.columns(2)
    with col1:
        st.success('小猿众包已成功进入！！！')
    with col2:
        if st.button('返回首页'):
            xiao_yuan.go_home()
            st.session_state.xiao_yuan_step = 1
            st.session_state.xiao_yuan_card_name = ''
            st.session_state.xiao_yuan_card = ''

    # 第一步：开始任务
    if st.session_state.xiao_yuan_step == 1:
        st.subheader(f'小猿第{st.session_state.xiao_yuan_step}步：获取任务信息！')
        cards = xiao_yuan.home()
        # st.write(cards)
        st.session_state.xiao_yuan_card_name = st.selectbox('请选择要执行的任务', cards.keys())  # 无阻塞，默认第一个数据
        st.write(st.session_state.xiao_yuan_card_name)
        if st.button('开始任务'):
            # 获得任务卡片
            st.session_state.xiao_yuan_card = cards[st.session_state.xiao_yuan_card_name]
            xiao_yuan.start(st.session_state.xiao_yuan_card)
            st.session_state.xiao_yuan_step = 2
            st.rerun()  # 刷新进入步骤2

    # 第二步：执行任务
    if st.session_state.xiao_yuan_step == 2 and '单题标答-审核' in st.session_state.xiao_yuan_card_name:
        st.subheader(f'小猿第{st.session_state.xiao_yuan_step}步：执行{st.session_state.xiao_yuan_card_name}任务')
        col1, col2 = st.columns(2)
        with col1:
            if st.button('审核正确'):
                xiao_yuan.go_question(st.session_state.xiao_yuan_card_name)
            if st.button('提交领下一任务'):
                xiao_yuan.compete('提交领下一任务')
        with col2:
            if st.button('审核错误'):
                pass
    if st.session_state.xiao_yuan_step == 2 and '3.0改错-补答' in st.session_state.xiao_yuan_card_name:
        st.subheader(f'小猿第{st.session_state.xiao_yuan_step}步：执行{st.session_state.xiao_yuan_card_name}任务')
        col1, col2 = st.columns(2)
        with col1:
            if st.button('审核正确'):
                pass
            if st.button('提交领下一任务'):
                pass
        with col2:
            if st.button('审核错误'):
                pass
            if st.button('返回首页'):
                pass
    else:
        st.write('自动化功能暂未开发！')
