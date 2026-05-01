import os
import asyncio
import streamlit as st

from langchain_core.messages import SystemMessage

from yuanai.core.lc import get_llm, dsllm, seed
from yuanai.core.chat import stream_agent_events, build_input_messages, build_chat_history, parse_session_message
from yuanai.tools import all_tools as in_tools
from yuanai.utils.image import process_uploaded_images
from yuanai.ui.components import display_message, load_css, show_loading_indicator, show_tool_status
from webui.app_core import initializing_state
from utils.data_path import root_path


INITIAL_STATE = {"messages": []}


def main():
    initializing_state(INITIAL_STATE)
    load_css()

    col1, col2 = st.columns([3, 1])

    llm = get_llm(
        col2.selectbox("选择模型", dsllm + seed, index=len(dsllm)),
        temperature=col2.slider("生成温度", 0.0, 1.0, 0.7, step=0.1),
        verbose=False,
        streaming=True
    )

    if col2.button("清空对话历史", type="secondary", width="stretch"):
        st.session_state.messages = []
        st.rerun()

    chat_container = col1.container(height=500, border=True)
    with chat_container:
        for msg in st.session_state.messages:
            role, content, images, reasoning = parse_session_message(msg)
            avatar = "👤" if role == "user" else os.path.join(root_path(), "data/file/img/home.ico")
            display_message(chat_container, role, content, images, avatar)

    latest_prompt = st.chat_input(
        "请输入你的问题（支持工具调用 + 多图上传）...",
        key="chat_input",
        accept_file="multiple",
        file_type=["jpg", "jpeg", "png"]
    )

    if latest_prompt:
        user_text = latest_prompt.text or ""
        uploaded_files = latest_prompt.files

        images_base64, errors = process_uploaded_images(uploaded_files)
        for error in errors:
            st.error(f"图片处理失败: {error}")

        st.session_state.messages.append(("user", user_text, images_base64, ""))
        with chat_container:
            display_message(chat_container, "user", user_text, images_base64, "👤")

        tools = in_tools
        system_message = SystemMessage(content="你是一个能调用工具的助手")
        chat_history = build_chat_history(st.session_state.messages[:-1])
        input_messages = build_input_messages(user_text, images_base64, chat_history, system_message)

        with chat_container:
            avatar = os.path.join(root_path(), "data/file/img/home.ico")
            with chat_container.chat_message("assistant", avatar=avatar):
                message_placeholder = st.empty()
                show_loading_indicator(message_placeholder)

                full_response = ""
                reasoning_content = ""

                async def run_stream():
                    nonlocal full_response, reasoning_content
                    async for event in stream_agent_events(llm, input_messages, tools):
                        if event["type"] == "token":
                            full_response += event["data"]
                            message_placeholder.markdown(full_response + "▌")
                        elif event["type"] == "tool_start":
                            show_tool_status("tool_start", event["data"]["name"])
                        elif event["type"] == "tool_end":
                            show_tool_status("tool_end", event["data"]["name"])
                        elif event["type"] == "done":
                            reasoning_content = event["data"].get("reasoning_content", "")
                        elif event["type"] == "error":
                            full_response = f"❌ 错误: {event['data']}"

                try:
                    asyncio.run(run_stream())
                    message_placeholder.markdown(full_response)
                except Exception as e:
                    full_response = f"请求出错：{str(e)}"
                    reasoning_content = ""
                    message_placeholder.markdown(full_response)

        if full_response:
            st.session_state.messages.append(("assistant", full_response, [], reasoning_content))

        st.rerun()


if __name__ == "__main__":
    main()