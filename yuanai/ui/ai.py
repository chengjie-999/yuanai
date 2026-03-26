import os
import asyncio
import streamlit as st

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from yuanai.core.lc import get_llm, get_langgraph_agent
from yuanai.tools import all_tools as tools
from utils import initializing_state
from utils.data_path import root_path

INITIAL_STATE = {"messages": []}


def get_chat_history():
    chat_history = []
    for role, content in st.session_state.messages:
        if role == "user":
            chat_history.append(HumanMessage(content=content))
        elif role == "assistant":
            chat_history.append(AIMessage(content=content))
    return chat_history


def main():
    initializing_state(INITIAL_STATE)

    st.write("🤖 小元AI助手")
    col1, col2 = st.columns([3, 1])

    llm = get_llm(
        col2.selectbox("选择模型", ['deepseek-chat', "deepseek-vl2", "deepseek-coder"], index=0),
        temperature=col2.slider("生成温度", 0.0, 1.5, 0.7, step=0.1),
        verbose=False,
        streaming=True
    )

    if col2.button("清空对话历史", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    chat_container = col1.container(height=500, border=True)
    with chat_container:
        for msg in st.session_state.messages:
            role, content = msg
            with st.chat_message(
                    role,
                    avatar="👤" if role == "user" else os.path.join(root_path(), "data/file/img/home.ico")
            ):
                st.markdown(content)

    latest_prompt = col1.chat_input("请输入你的问题（支持工具调用）...", key="chat_input")

    if latest_prompt:
        st.session_state.messages.append(("user", latest_prompt))
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(latest_prompt)

        with chat_container:
            with st.chat_message(
                    "assistant",
                    avatar=os.path.join(root_path(), "data/file/img/home.ico")
            ):
                message_placeholder = st.empty()
                full_response = ""

                agent = get_langgraph_agent(llm, tools)
                system_message = SystemMessage(content="你是一个能调用工具的助手")
                chat_history = get_chat_history()
                input_messages = [system_message] + chat_history + [HumanMessage(content=latest_prompt)]

                async def stream_agent():
                    nonlocal full_response
                    try:
                        # 使用 astream_events 捕获流式事件
                        async for event in agent.astream_events(
                                {"messages": input_messages},
                                version="v2"  # 使用 v2 版本事件（推荐）
                        ):
                            # 捕获 LLM 流式 token
                            if event["event"] == "on_chat_model_stream":
                                chunk = event["data"]["chunk"]
                                # chunk 可能是 AIMessageChunk，提取 content
                                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                                if token:
                                    full_response += token
                                    message_placeholder.markdown(full_response + "▌")
                            # 捕获工具调用开始/结束（可选）
                            elif event["event"] == "on_tool_start":
                                st.info(f"🔧 正在调用工具: {event['name']}")
                            elif event["event"] == "on_tool_end":
                                st.success(f"✅ 工具调用完成: {event['name']}")
                            # 捕获最终消息（确保最后完整显示）
                            elif event["event"] == "on_chain_end" and "messages" in event.get("data", {}).get("output",
                                                                                                              {}):
                                # 如果有最终输出且之前没有流式 token（某些情况下）
                                if not full_response:
                                    last_msg = event["data"]["output"]["messages"][-1]
                                    if hasattr(last_msg, "content"):
                                        full_response = last_msg.content
                                        message_placeholder.markdown(full_response)
                        # 移除光标
                        if full_response:
                            message_placeholder.markdown(full_response)
                        return full_response
                    except Exception as e:
                        error_msg = f"❌ 出错：{str(e)}"
                        message_placeholder.markdown(error_msg)
                        return error_msg

                # 运行异步函数
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    full_response = loop.run_until_complete(stream_agent())
                except Exception as e:
                    full_response = f"请求出错：{str(e)}"
                    message_placeholder.markdown(full_response)

        if full_response:
            st.session_state.messages.append(("assistant", full_response))


if __name__ == "__main__":
    main()
