import random
import time

import streamlit as st

from app_core import initializing_state, reset_to_initial
from spiderlx.core.parse.xiaoyuan import SeleniumXiaoYuan

INITIAL_STATE = {
    "xiao_yuan_card_name": '',
    "xiao_yuan_card": "",
    "xiao_yuan_like": '单题标答-审核',
    "xiao_yuan_auto": False,
    "xiao_yuan_count": 0,
    "xiao_yuan_step": 1,
    "xiao_yuan_qa": ['https://xyzb.yuanfudao.com/img/task-banner.53406e80.png'],
    "xiao_yuan_false_causes": ['格式问题', "举报"],
    "xiao_yuan_false_cause": '格式问题',
}  # 初始状态


def home_start(xiao_yuan, output_placeholder=None):
    go_on = xiao_yuan.start(st.session_state.xiao_yuan_card)
    st.session_state.xiao_yuan_count += 1
    if output_placeholder:
        context = {'任务': st.session_state.xiao_yuan_card_name,
                   '自动点击次数': st.session_state.xiao_yuan_count,
                   '是否成功': go_on
                   }
        output_placeholder.write(context)
    if go_on:
        st.session_state.xiao_yuan_step = 2
        st.session_state.xiao_yuan_auto = False
        st.session_state.xiao_yuan_count = 0
        st.rerun()  # 刷新进入步骤2
    return go_on


def go_one(xiao_yuan):
    """
    首页第一步
    :param xiao_yuan: 小猿众包
    :return:
    """

    st.subheader(f'小猿第{st.session_state.xiao_yuan_step}步：获取主页任务信息！')
    if not st.session_state.xiao_yuan_auto:
        if st.button('开启自动开始任务'):
            st.session_state.xiao_yuan_auto = True
            st.rerun()
    else:
        if st.button('关闭自动开始任务'):
            st.session_state.xiao_yuan_auto = False
            st.rerun()
    cards = xiao_yuan.home(st.session_state.xiao_yuan_like)
    # st.write(cards)
    cards_name = cards.keys()
    st.session_state.xiao_yuan_card_name = st.selectbox('请选择要执行的任务', cards_name, len(cards_name) - 1)  # 无阻塞，默认第一个数据
    st.session_state.xiao_yuan_like = st.session_state.xiao_yuan_card_name
    # 获得任务卡片
    st.session_state.xiao_yuan_card = cards[st.session_state.xiao_yuan_card_name]
    st.write(st.session_state.xiao_yuan_card_name)
    if st.button(f'开始任务'):
        go_on = home_start(xiao_yuan)
        context = {'任务': st.session_state.xiao_yuan_card_name,
                   '点击次数': st.session_state.xiao_yuan_count,
                   '是否成功': go_on
                   }
        st.write(context)

    output_placeholder = st.empty()
    while st.session_state.xiao_yuan_auto:
        time.sleep(random.randint(6, 15))
        go_on = home_start(xiao_yuan, output_placeholder)
        if go_on:
            break


def main():
    """
    小猿ui主页
    :return:
    """
    initializing_state(INITIAL_STATE)

    xiao_yuan = SeleniumXiaoYuan(st.session_state.web_driver)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.image("https://xyzb.yuanfudao.com/img/logo.24003130.png", width=150)
    with col2:
        pass
    with col3:
        if st.button('返回首页'):
            xiao_yuan.go_home()
            reset_to_initial(INITIAL_STATE)
            # st.session_state.xiao_yuan_auto = True
            st.rerun()

    # 第一步：首页开始任务
    if st.session_state.xiao_yuan_step == 1:
        go_one(xiao_yuan)

    # 第二步：执行任务
    if st.session_state.xiao_yuan_step == 2 and '单题标答-审核' in st.session_state.xiao_yuan_card_name:
        st.subheader(f'小猿第{st.session_state.xiao_yuan_step}步：执行{st.session_state.xiao_yuan_card_name}任务')
        st.session_state.xiao_yuan_qa = xiao_yuan.question_info()

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
                    reset_to_initial(INITIAL_STATE)
                    st.session_state.xiao_yuan_auto = True
                    st.rerun()
                # time.sleep(2)
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
            if st.button('查看原题目', use_container_width=True):
                xiao_yuan.to_detail()
            if st.button('关闭原题目', use_container_width=True):
                xiao_yuan.close_detail()
            if st.button('审核正确', type='primary', use_container_width=True):
                xiao_yuan.go_question(st.session_state.xiao_yuan_card_name)
            if st.button('提交领下一任务', use_container_width=True):
                go_on = xiao_yuan.box()
                if not go_on:
                    st.session_state.xiao_yuan_step = 1
                    st.rerun()
            if st.button('审核错误'):
                xiao_yuan.go_question(st.session_state.xiao_yuan_card_name, true=False)
        with col2:
            pass
    st.image(st.session_state.xiao_yuan_qa)
