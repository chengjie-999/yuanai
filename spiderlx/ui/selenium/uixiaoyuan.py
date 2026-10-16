import base64
import os
import random
import time
import asyncio

import streamlit as st

from langchain_core.messages import HumanMessage, SystemMessage

from spiderlx.ui.selenium.resource import get_driver
from webui.app_core import initializing_state, reset_to_initial
from spiderlx.auto.web.selenium.xiaoyuan.xiaoyuan import SeleniumXiaoYuan, SingleAuditHandler
from spiderlx.auto.canvas.core import scroll as canvas_scroll
from yuanai_core.core.chat import stream_agent_with_inject
from yuanai_core.core.lc import get_llm
from yuanai_core.tools import all_tools as in_tools
from agent.audit import build_audit_prompt, save_feedback

INITIAL_STATE = {
    "xiao_yuan_card_name": '',
    "xiao_yuan_card_selector": "",
    "xiao_yuan_like": '单题标答-审核',
    "xiao_yuan_auto": False,
    "xiao_yuan_ai": False,
    "xiao_yuan_count": 0,
    "xiao_yuan_step": 1,
    "xiao_yuan_qa": ['https://xyzb.yuanfudao.com/img/task-banner.53406e80.png'],
    "xiao_yuan_false_causes": ['格式问题占比较多', "举报", '文本压线', '黄框压题干', '最终答案', '不独立', '出框', '少答案', '字太小', '答案错'],
    "xiao_yuan_false_cause": '格式问题',
}

AUDIT_MODEL = 'doubao-seed-2-0-pro-260215'


def home_start(xiao_yuan, xiao_yuan_card, output_placeholder=None):
    go_on = xiao_yuan.start(xiao_yuan_card)
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

    xiao_yuan_card = cards[st.session_state.xiao_yuan_card_name]
    st.session_state.xiao_yuan_card_selector = st.session_state.xiao_yuan_card_name

    st.write("当前任务：", st.session_state.xiao_yuan_card_name)

    if st.button(f'开始任务'):
        go_on = home_start(xiao_yuan, xiao_yuan_card)
        context = {
            '任务': st.session_state.xiao_yuan_card_name,
            '点击次数': st.session_state.xiao_yuan_count,
            '是否成功': go_on
        }
        st.write(context)

    output_placeholder = st.empty()
    while st.session_state.xiao_yuan_auto:
        time.sleep(random.randint(6, 15))
        cards_new = xiao_yuan.home_card(st.session_state.xiao_yuan_like)
        current_card = cards_new[st.session_state.xiao_yuan_card_name]
        go_on = home_start(xiao_yuan, current_card, output_placeholder)
        if go_on:
            break


def save_audit_to_chat(user_text, user_images, assistant_text, reasoning=""):
    """将审核对话同步到聊天模块的消息记录"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    st.session_state.messages.append(("user", user_text, user_images, ""))
    st.session_state.messages.append(("assistant", assistant_text, [], reasoning))


def render_ai_audit_chat(qa_images, sa):
    if st.button("🤖 AI审核", width="stretch", type="primary"):
        for key in list(st.session_state.keys()):
            if key.startswith('feedback_') or key.startswith('_audit_'):
                del st.session_state[key]
        st.session_state["_audit_running"] = True
        st.rerun()

    if not st.session_state.get("_audit_running"):
        if st.session_state.get("_audit_done"):
            render_feedback_ui(sa)
        return

    if st.session_state.get("_audit_started"):
        st.info("⏳ AI 审核运行中，请等待完成...")
        return

    st.session_state["_audit_started"] = True

    # 审核 Agent 只暴露阅卷工具，不暴露提交/驳回（由反馈按钮处理）
    audit_tools = [t for t in in_tools if t.name not in ("submit_task", "confirm_rejection")]

    # 同步现有浏览器到工具模块，避免新开浏览器
    from spiderlx.core.browser_manager import browser_manager
    browser = get_driver()
    browser_manager.set_browser(browser)

    chat_container = st.container(border=True)

    with chat_container:
        with st.chat_message("user"):
            st.write("请审核这道题，自动判断并处理")
            cols = st.columns(min(len(qa_images), 3))
            for i, img in enumerate(qa_images):
                with cols[i % 3]:
                    st.image(img, width=150)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("⏳ AI 正在审核中...")

            llm = get_llm(AUDIT_MODEL, temperature=0.1, verbose=False, streaming=True)
            normalize_images = []
            for item in qa_images:
                if isinstance(item, bytes):
                    b64 = base64.b64encode(item).decode('utf-8')
                    normalize_images.append(f"data:image/png;base64,{b64}")
                elif isinstance(item, str):
                    if item.startswith('data:image'):
                        normalize_images.append(item)
                    elif os.path.exists(item):
                        with open(item, 'rb') as f:
                            b64 = base64.b64encode(f.read()).decode('utf-8')
                        normalize_images.append(f"data:image/png;base64,{b64}")
                    else:
                        normalize_images.append(item)

            user_content = [{"type": "text", "text": "请审核这道题，判断标注是否正确，然后自动处理。"}]
            for img_url in normalize_images:
                user_content.append({"type": "image_url", "image_url": {"url": img_url}})

            messages = [
                SystemMessage(content=build_audit_prompt()),
                HumanMessage(content=user_content),
            ]

            full_response = ""
            reasoning_content = ""

            def after_tool(names):
                if any(t in names for t in ("scroll_canvas", "zoom_question", "restore_question_view", "click_canvas")):
                    time.sleep(0.5)
                    try:
                        img_bytes = sa.driver.get_screenshot_as_png()
                        b64 = base64.b64encode(img_bytes).decode('utf-8')
                        img_url = f"data:image/png;base64,{b64}"
                        label = "已滚动" if "scroll_canvas" in names else "已缩放"
                        return [HumanMessage(content=[
                            {"type": "text", "text": f"{label}并重新截图，请查看完整题目："},
                            {"type": "image_url", "image_url": {"url": img_url}}
                        ])]
                    except Exception:
                        pass
                return None

            try:
                async def run_stream():
                    nonlocal full_response, reasoning_content
                    async for event in stream_agent_with_inject(llm, messages, audit_tools, after_tool):
                        if event["type"] == "token":
                            full_response += event["data"]
                            placeholder.markdown(full_response + "▌")
                        elif event["type"] == "tool_start":
                            st.info(f"🔧 调用工具: {event['data']['name']}")
                        elif event["type"] == "tool_end":
                            st.success(f"✅ 工具完成: {event['data']['name']}")
                        elif event["type"] == "inject":
                            st.info(f"📷 已获取新截图，继续分析...")
                        elif event["type"] == "done":
                            reasoning_content = event["data"].get("reasoning_content", "")

                asyncio.run(run_stream())
            except Exception as e:
                import traceback
                traceback.print_exc()
                full_response = f"❌ 审核执行失败: {str(e)}"

            if full_response:
                placeholder.markdown(full_response)
                st.session_state["_audit_done"] = True
                st.session_state["_audit_running"] = False
                st.session_state.pop("_audit_started", None)
                st.session_state["_audit_result_text"] = full_response
                save_audit_to_chat("请审核这道题，判断标注是否正确", qa_images, full_response, reasoning_content)

    if st.session_state.get("_audit_done"):
        render_feedback_ui(sa)


def render_feedback_ui(sa):
    """渲染操作后的反馈确认界面"""
    st.markdown("---")
    st.markdown("### 操作是否正确？")

    col_yes, col_no, col_skip = st.columns([1, 1, 2])

    result_text = st.session_state.get("_audit_result_text", "")

    with col_yes:
        if st.button("✅ 正确，没问题", width="stretch", type="primary"):
            sa.compete("提交领下一任务")
            save_feedback(result_text, True, "用户确认正确")
            if "messages" not in st.session_state:
                st.session_state.messages = []
            st.session_state.messages.append(("user", "AI审核结果正确，已确认提交任务", [], ""))
            st.session_state.messages.append(("assistant", "✅ 已收到确认，任务已提交。", [], ""))
            _clear_audit_state()
            st.rerun()

    with col_no:
        if st.button("❌ 有误，我来纠正", width="stretch"):
            st.session_state["_feedback_correcting"] = True

    with col_skip:
        if st.button("⏭ 跳过，下一题", width="stretch"):
            sa.question_restore()
            if "messages" not in st.session_state:
                st.session_state.messages = []
            st.session_state.messages.append(("user", "AI审核被跳过，未提交", [], ""))
            st.session_state.messages.append(("assistant", "⏭ 已跳过，等待下一题。", [], ""))
            _clear_audit_state()
            st.rerun()

    if st.session_state.get("_feedback_correcting"):
        with st.form(key="correction_form"):
            cause = st.text_input("错误原因", placeholder="输入具体的错误原因...")
            note = st.text_area("详细说明（可选）：", placeholder="请描述具体问题...")
            col_submit, col_cancel = st.columns(2)
            with col_submit:
                if st.form_submit_button("📤 驳回并提交反馈", type="primary"):
                    try:
                        sa.compete("整题驳回", cause=cause)
                    except Exception as e:
                        st.error(f"驳回操作失败: {e}")
                    save_feedback(result_text, False, f"{cause}: {note}")
                    if "messages" not in st.session_state:
                        st.session_state.messages = []
                    st.session_state.messages.append((
                        "user", f"AI审核结果有误，纠正为: {cause}\n说明: {note}", [], ""
                    ))
                    st.session_state.messages.append(("assistant", "✅ 已收到纠正反馈，我会学习改进。", [], ""))
                    _clear_audit_state()
                    st.rerun()
            with col_cancel:
                if st.form_submit_button("取消"):
                    st.session_state["_feedback_correcting"] = False
                    st.rerun()


def _clear_audit_state():
    st.session_state["_audit_running"] = False
    st.session_state["_audit_done"] = False
    st.session_state.pop("_audit_started", None)
    st.session_state.pop("_audit_result_text", None)
    st.session_state.pop("_feedback_correcting", None)


def render_action_buttons(sa, driver):
    with st.expander("手动操作", expanded=False):
        col_ref, col_down, col_up, col_zoom = st.columns(4)
        with col_ref:
            if st.button("🔄 刷新", width="stretch"):
                driver.refresh()
                st.rerun()
        with col_down:
            if st.button("⬇ 向下滚动", width="stretch"):
                canvas_scroll()
        with col_up:
            if st.button("⬆ 向上滚动", width="stretch"):
                canvas_scroll(direction="up")
        with col_zoom:
            if st.button("🔍 缩小", width="stretch"):
                sa.question_resize()

        st.markdown("---")
        col_submit, col_reject = st.columns(2)
        with col_submit:
            if st.button("✅ 审核正确", width="stretch", type="primary"):
                sa.quick_true_handle(False)
                sa.question_restore()
        with col_reject:
            cause = st.selectbox('错误原因', st.session_state.xiao_yuan_false_causes, key="false_cause_select")
            st.session_state.xiao_yuan_false_cause = cause
            if st.button("❌ 整题驳回", width="stretch"):
                go_on = sa.compete('整题驳回', cause=cause)
                if not go_on:
                    st.session_state.xiao_yuan_step = 1

        if st.button("提交领下一任务", width="stretch", type="secondary"):
            go_on = sa.compete('提交领下一任务')
            if not go_on:
                reset_to_initial(INITIAL_STATE)
                st.session_state.xiao_yuan_auto = True
                st.rerun()
            st.rerun()

        if st.button("确定驳回", width="stretch"):
            sa.rejection_confirmation()

        if st.button('展示标记答案', width="stretch"):
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.xiao_yuan_qa = sa.question_info()
                s_mark = st.session_state.xiao_yuan_qa[1]
                st.image(s_mark, caption='独立答案')
                marks = st.session_state.xiao_yuan_qa[2:]
                for i in range(len(marks)):
                    st.image(marks[i], caption=f'答案{i}')


def main():
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

    if st.session_state.xiao_yuan_step == 1:
        go_one(xiao_yuan)

    if st.session_state.xiao_yuan_step == 2 and '单题标答-审核' in st.session_state.xiao_yuan_card_name:
        st.subheader(f'{st.session_state.xiao_yuan_card_name}')

        try:
            st.session_state.xiao_yuan_qa = sa.question_info(screenshot=False)
        except Exception as e:
            st.write(f"获取题目信息失败：{str(e)}")
            st.session_state.xiao_yuan_qa = ['https://xyzb.yuanfudao.com/img/task-banner.53406e80.png']

        qa_images = st.session_state.xiao_yuan_qa

        if len(qa_images) >= 1:
            st.image(qa_images[0], caption='题目截图', width="stretch")

        st.image(st.session_state.xiao_yuan_qa[1], caption='参考答案')

        render_ai_audit_chat(qa_images, sa)

        st.markdown("---")
        render_action_buttons(sa, driver)

    if st.session_state.xiao_yuan_step == 2 and '3.0改错-补答' in st.session_state.xiao_yuan_card_name:
        st.subheader(f'{st.session_state.xiao_yuan_card_name}')
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
        st.subheader(f'{st.session_state.xiao_yuan_card_name}')
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