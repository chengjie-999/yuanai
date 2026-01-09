import streamlit as st
from spider_lx.parse_data.xiao_yuan import XiaoYuan

if "xiao_yuan" not in st.session_state:
    st.session_state.xiao_yuan = ''  #

if "xiao_yuan_card_name" not in st.session_state:
    st.session_state.xiao_yuan_card = ''  #
    st.session_state.xiao_yuan = ''  #

if "xiao_yuan_card" not in st.session_state:
    st.session_state.xiao_yuan_card = ''  #

if "xiao_yuan_step" not in st.session_state:
    st.session_state.xiao_yuan_step = 1  #


def main():
    st.success('小猿众包已成功进入！！！')
    xiao_yuan = XiaoYuan(st.session_state.web_driver)

    # 第一步：开始任务
    if st.session_state.xiao_yuan_step == 1:
        cards = xiao_yuan.home()
        st.write(cards)
        st.session_state.xiao_yuan_card_name = st.selectbox('请选择要执行的任务', cards.keys())
        st.write(st.session_state.xiao_yuan_card_name)
        # 获得任务卡片
        st.session_state.xiao_yuan_card = cards[st.session_state.xiao_yuan_card]
        xiao_yuan.start(st.session_state.xiao_yuan_card)

    # 第二部：执行任务
    if st.session_state.xiao_yuan_step == 2:
        xiao_yuan.go_question(st.session_state.xiao_yuan_card_name)
