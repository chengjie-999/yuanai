import os
import streamlit as st

from langchain_core.messages import HumanMessage, AIMessage

from yuanai.core.lc import get_llm, get_prompt, get_agent_executor
from yuanai.tools import all_tools as tools
from utils import initializing_state
from utils.data_path import root_path

# ========== 初始化状态 ==========
INITIAL_STATE = {
    "messages": [],  # 格式：[(role, content), ...]
}


def get_chart_history():
    # 准备对话历史
    chat_history = []
    for role, content in st.session_state.messages[:-1]:  # 排除当前输入
        if role == "user":
            chat_history.append(HumanMessage(content=content))
        elif role == "assistant":
            chat_history.append(AIMessage(content=content))
    return chat_history


def main():
    initializing_state(INITIAL_STATE)

    st.write("🤖 小元AI助手")
    col1, col2 = st.columns([3, 1])

    # 1. 配置 LLM（非流式）
    llm = get_llm(
        base_url="https://api.deepseek.com/v1",
        model_name=col2.selectbox("选择模型", ['deepseek-chat', "deepseek-vl2", "deepseek-coder"], index=0),
        temperature=col2.slider("生成温度", 0.0, 1.0, 0.7, step=0.1),
        verbose=False
    )

    # 清空对话按钮
    if col2.button("清空对话历史", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    # 2. 渲染历史消息
    chat_container = col1.container(height=500, border=True)
    with chat_container:
        for msg in st.session_state.messages:
            role, content = msg
            with st.chat_message(
                    role,
                    avatar="👤" if role == "user" else os.path.join(root_path(), "data/file/img/home.ico")
            ):
                st.markdown(content)
            st.markdown("<br>", unsafe_allow_html=True)

    # 3. 处理用户输入
    input_placeholder = col1.empty()
    with input_placeholder:
        latest_prompt = st.chat_input("请输入你的问题（支持工具调用）...", key="chat_input")

    if latest_prompt:
        # 存储用户消息
        st.session_state.messages.append(("user", latest_prompt))

        # 实时显示用户消息
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(latest_prompt)
            st.markdown("<br>", unsafe_allow_html=True)

        # 4. 调用 Agent
        with chat_container:
            with st.chat_message(
                    "assistant",
                    avatar=os.path.join(root_path(), "data/file/img/home.ico")
            ):

                chat_history = get_chart_history()

                # 初始化 Agent 执行器
                agent_executor = get_agent_executor(
                    llm=llm,
                    tools=tools,
                    prompt=get_prompt()
                )

                try:
                    result = agent_executor.invoke({
                        "input": latest_prompt,
                        "chat_history": chat_history,
                        "agent_scratchpad": []
                    })
                    full_response = result["output"]
                except Exception as e:
                    full_response = f"请求出错：{str(e)}"

                st.markdown(full_response)
                st.markdown("<br>", unsafe_allow_html=True)

        # 存储 AI 响应
        st.session_state.messages.append(("assistant", full_response))
        st.rerun()


if __name__ == "__main__":
    main()