import streamlit as st
from spider_lx.auto.web.selenium.xiao_yuan import XiaoYuan


def main():
    st.divider()

    if "xiao_yuan_card_name" not in st.session_state:
        st.session_state.xiao_yuan_card = ''  #

    if "xiao_yuan_card" not in st.session_state:
        st.session_state.xiao_yuan_card = ''  #

    if "xiao_yuan_step" not in st.session_state:
        st.session_state.xiao_yuan_step = 1  # 小猿操作步骤
    if "xiao_yuan_false_causes" not in st.session_state:
        st.session_state.xiao_yuan_false_causes = ['格式问题']  # 小猿题目错误原因
    if "xiao_yuan_false_cause" not in st.session_state:
        st.session_state.xiao_yuan_false_cause = '格式问题'  # 小猿题目错误原因

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
        cards_name = cards.keys()
        st.session_state.xiao_yuan_card_name = st.selectbox('请选择要执行的任务', cards_name, len(cards_name) - 1)  # 无阻塞，默认第一个数据
        st.write(st.session_state.xiao_yuan_card_name)
        if st.button('开始任务'):
            # 获得任务卡片
            st.session_state.xiao_yuan_card = cards[st.session_state.xiao_yuan_card_name]
            go_on = xiao_yuan.start(st.session_state.xiao_yuan_card)
            if go_on:
                st.session_state.xiao_yuan_step = 2
                st.rerun()  # 刷新进入步骤2

    # 第二步：执行任务
    if st.session_state.xiao_yuan_step == 2 and '单题标答-审核' in st.session_state.xiao_yuan_card_name:
        st.subheader(f'小猿第{st.session_state.xiao_yuan_step}步：执行{st.session_state.xiao_yuan_card_name}任务')

        col1, col2 = st.columns(2)
        with col1:
            if st.button('审核错误'):
                pass
            if st.button('缩小'):
                xiao_yuan.question_resize()
            st.divider()
            if st.button('审核正确'):
                xiao_yuan.go_question(st.session_state.xiao_yuan_card_name)
                xiao_yuan.question_restore()

            if st.button('提交领下一任务'):
                go_on = xiao_yuan.compete('提交领下一任务')
                if not go_on:
                    st.session_state.xiao_yuan_step = 1
                    st.rerun()
            if st.button('整题驳回'):
                st.session_state.xiao_yuan_false_cause = st.selectbox('', st.session_state.xiao_yuan_false_causes)
                go_on = xiao_yuan.compete('整题驳回', cause=st.session_state.xiao_yuan_false_cause)
                st.write(st.session_state.xiao_yuan_false_cause)
                if st.button('确定'):
                    xiao_yuan.rejection_confirmation()
                if not go_on:
                    st.session_state.xiao_yuan_step = 1
        with col2:
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
    if st.session_state.xiao_yuan_step == 2 and '抄写图形题-补答审核' in st.session_state.xiao_yuan_card_name:
        st.subheader(f'小猿第{st.session_state.xiao_yuan_step}步：执行{st.session_state.xiao_yuan_card_name}任务')
        col1, col2 = st.columns(2)
        with col1:
            if st.button('审核错误'):
                xiao_yuan.go_question(st.session_state.xiao_yuan_card_name, true=False)
            if st.button('审核正确'):
                xiao_yuan.go_question(st.session_state.xiao_yuan_card_name)
            if st.button('提交领下一任务'):
                xiao_yuan.box()
        with col2:
            pass
