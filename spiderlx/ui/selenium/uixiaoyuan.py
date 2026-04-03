import random
import time

import streamlit as st

from spiderlx.ui.selenium.resource import get_driver
from webui.app_core import initializing_state, reset_to_initial
from spiderlx.auto.web.selenium.xiaoyuan.xiaoyuan import SeleniumXiaoYuan, SingleAuditHandler

INITIAL_STATE = {
    "xiao_yuan_card_name": '',
    "xiao_yuan_card_selector": "",  # 👈 改这里，存定位符，不存 WebElement
    "xiao_yuan_like": '单题标答-审核',
    "xiao_yuan_auto": False,
    "xiao_yuan_count": 0,
    "xiao_yuan_step": 1,
    "xiao_yuan_qa": ['https://xyzb.yuanfudao.com/img/task-banner.53406e80.png'],
    "xiao_yuan_false_causes": ['格式问题', "举报", '文本压线', '黄框压题干', '最终答案', '不独立', '出框', '少答案', '字太小', '答案错'],
    "xiao_yuan_false_cause": '格式问题',
}


def home_start(xiao_yuan, xiao_yuan_card, output_placeholder=None):
    """
    回首页
    """
    go_on = xiao_yuan.start(xiao_yuan_card)  # 👈 直接用，不从session取
    st.session_state.xiao_yuan_count += 1

    if output_placeholder:
        context = {
            '任务': st.session_state.xiao_yuan_card_name,
            '自动点击次数': st.session_state.xiao_yuan_count,
            '是否成功': go_on
        }
        output_placeholder.write(context)

    if go_on:
        st.session_state.xiao_yuan_step = 2
        st.session_state.xiao_yuan_auto = False
        st.session_state.xiao_yuan_count = 0
        st.rerun()
    return go_on


def go_one(xiao_yuan):
    st.subheader(f'小猿第{st.session_state.xiao_yuan_step}步：获取主页任务信息！')

    if not st.session_state.xiao_yuan_auto:
        if st.button('开启自动开始任务'):
            st.session_state.xiao_yuan_auto = True
            st.rerun()
    else:
        if st.button('关闭自动开始任务'):
            st.session_state.xiao_yuan_auto = False
            st.rerun()

    cards = xiao_yuan.home_card(st.session_state.xiao_yuan_like)
    cards_name = list(cards.keys())
    st.session_state.xiao_yuan_card_name = st.selectbox('请选择要执行的任务', cards_name, index=len(cards_name) - 1)
    st.session_state.xiao_yuan_like = st.session_state.xiao_yuan_card_name

    # 👇 核心修复：不存 WebElement，只存名字！需要用时重新获取
    xiao_yuan_card = cards[st.session_state.xiao_yuan_card_name]
    st.session_state.xiao_yuan_card_selector = st.session_state.xiao_yuan_card_name  # 用名字定位

    st.write("当前任务：", st.session_state.xiao_yuan_card_name)

    if st.button(f'开始任务'):
        go_on = home_start(xiao_yuan, xiao_yuan_card)  # 👈 直接传，不存session
        context = {
            '任务': st.session_state.xiao_yuan_card_name,
            '点击次数': st.session_state.xiao_yuan_count,
            '是否成功': go_on
        }
        st.write(context)

    output_placeholder = st.empty()
    while st.session_state.xiao_yuan_auto:
        time.sleep(random.randint(6, 15))
        # 每次循环 重新获取卡片，不使用缓存的 WebElement
        cards_new = xiao_yuan.home_card(st.session_state.xiao_yuan_like)
        current_card = cards_new[st.session_state.xiao_yuan_card_name]
        go_on = home_start(xiao_yuan, current_card, output_placeholder)
        if go_on:
            break


def main():
    """
    小猿ui主页
    :return:
    """
    initializing_state(INITIAL_STATE)
    driver = get_driver()

    xiao_yuan = SeleniumXiaoYuan(driver.driver)
    sa = SingleAuditHandler(xiao_yuan)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.image("https://xyzb.yuanfudao.com/img/logo.24003130.png", width=150)
    with col2:
        if st.button('重载'):
            st.rerun()
    with col3:
        if st.button('返回首页'):
            xiao_yuan.go_home()
            reset_to_initial(INITIAL_STATE)
            st.rerun()

    # 第一步：首页开始任务
    if st.session_state.xiao_yuan_step == 1:
        go_one(xiao_yuan)

    # 第二步：执行任务
    if st.session_state.xiao_yuan_step == 2 and '单题标答-审核' in st.session_state.xiao_yuan_card_name:
        st.subheader(f'小猿第{st.session_state.xiao_yuan_step}步：执行{st.session_state.xiao_yuan_card_name}任务')
        st.session_state.xiao_yuan_qa = sa.question_info(screenshot=False)
        st.image(st.session_state.xiao_yuan_qa[0], caption='界面')
        col1, col2, col3, col4, col5 = st.columns(5)
        if col4.button(f'刷新'):
            driver = get_driver()
            r = driver.refresh()
            st.write(r)
        if col3.button('缩小'):
            sa.question_resize()

        if col1.button('审核正确'):
            sa.quick_true_handle(False)
            sa.question_restore()

        if col2.button('提交领下一任务'):
            go_on = sa.compete('提交领下一任务')
            if not go_on:
                reset_to_initial(INITIAL_STATE)
                st.session_state.xiao_yuan_auto = True
                st.rerun()
            # time.sleep(2)
            st.rerun()

        st.session_state.xiao_yuan_false_cause = col5.selectbox('错误原因', st.session_state.xiao_yuan_false_causes)
        if col5.button('整题驳回'):
            st.write('错误理由：', st.session_state.xiao_yuan_false_cause)
            go_on = sa.compete('整题驳回', cause=st.session_state.xiao_yuan_false_cause)
            if not go_on:
                st.session_state.xiao_yuan_step = 1
        if col5.button('确定驳回'):
            sa.rejection_confirmation()
        if st.button('展示标记答案'):
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.xiao_yuan_qa = sa.question_info()
                s_mark = st.session_state.xiao_yuan_qa[1]
                st.image(s_mark, caption='独立答案')
                marks = st.session_state.xiao_yuan_qa[2:]
                for i in range(len(marks)):
                    st.image(marks[i], caption=f'答案{i}')

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
            if st.button('查看原题目', width='stretch'):
                xiao_yuan.to_detail()
            if st.button('关闭原题目', width='stretch'):
                xiao_yuan.close_detail()
            if st.button('审核正确', type='primary', width='stretch'):
                xiao_yuan.go_question(st.session_state.xiao_yuan_card_name)
            if st.button('提交领下一任务', width='stretch'):
                go_on = xiao_yuan.box()
                if not go_on:
                    st.session_state.xiao_yuan_step = 1
                    st.rerun()
            if st.button('审核错误'):
                xiao_yuan.go_question(st.session_state.xiao_yuan_card_name, true=False)
        with col2:
            pass
    if len(st.session_state.xiao_yuan_qa) >= 2:
        st.image(st.session_state.xiao_yuan_qa[1], caption='参考答案')
    else:
        st.image(st.session_state.xiao_yuan_qa[0], caption='界面')
