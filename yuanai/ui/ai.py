import os.path

import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage
from langchain.callbacks.base import BaseCallbackHandler

from utils import initializing_state
from utils.data_path import root_path
from utils.sensitive_data import get_api_key


# ========== 自定义Streamlit流式回调处理器 ==========
# 适配LangChain的流式输出到Streamlit界面
class StreamlitStreamingCallback(BaseCallbackHandler):
    def __init__(self, placeholder, container):
        self.placeholder = placeholder
        self.container = container
        self.full_response = ""

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """当收到新token时更新界面"""
        self.full_response += token
        self.placeholder.markdown(self.full_response + "▌")


INITIAL_STATE = {
    "messages": [],
}


def main():
    initializing_state(INITIAL_STATE)

    st.write("🤖 小元AI助手")
    col1, col2 = st.columns([3, 1])

    # ========== 1. 用LangChain初始化LLM（替代原生OpenAI客户端） ==========
    llm = ChatOpenAI(
        api_key=get_api_key(),
        base_url="https://api.deepseek.com/v1",  # 保留deepseek接口
        model_name=col2.selectbox("选择模型", ['deepseek-chat', "deepseek-vl2", "deepseek-coder"], index=0),
        temperature=col2.slider("生成温度", 0.0, 1.0, 0.7, step=0.1),
        streaming=True,  # 开启流式输出
        verbose=False
    )

    # 清空对话按钮
    if col2.button("清空对话历史", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    # 聊天区域
    chat_container = col1.container(height=500, border=True)
    with chat_container:
        # 显示历史消息
        for idx, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"], avatar="👤" if message["role"] == "user" else os.path.join(root_path(), "data/file/img/home.ico")):
                st.markdown(message["content"])
            st.markdown("<br>", unsafe_allow_html=True)

    # 底部输入框
    input_placeholder = col1.empty()
    with input_placeholder:
        prompt = st.chat_input("请输入你的问题...", key="chat_input")

    # ========== 2. 处理用户输入（LangChain消息格式适配） ==========
    if prompt:
        # 添加用户消息到会话状态
        st.session_state.messages.append({"role": "user", "content": prompt})

        # 实时显示用户消息
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)
            st.markdown("<br>", unsafe_allow_html=True)

        # ========== 3. LangChain流式调用LLM ==========
        with chat_container:
            with st.chat_message("assistant", avatar=os.path.join(root_path(), "data/file/img/home.ico")):
                message_placeholder = st.empty()
                # 初始化自定义流式回调
                stream_callback = StreamlitStreamingCallback(message_placeholder, chat_container)

                # 转换历史消息为LangChain标准格式
                langchain_messages = []
                for msg in st.session_state.messages:
                    if msg["role"] == "user":
                        langchain_messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        langchain_messages.append(AIMessage(content=msg["content"]))

                # 调用LLM（流式输出）
                try:
                    response = llm.invoke(
                        langchain_messages,
                        config={"callbacks": [stream_callback]}  # 绑定回调处理器
                    )
                    full_response = response.content
                    # 最终移除光标，显示完整响应
                    message_placeholder.markdown(full_response)
                except Exception as e:
                    full_response = f"请求出错：{str(e)}"
                    message_placeholder.markdown(full_response)

                st.markdown("<br>", unsafe_allow_html=True)

        # 添加AI响应到会话历史
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.rerun()


if __name__ == "__main__":
    main()
