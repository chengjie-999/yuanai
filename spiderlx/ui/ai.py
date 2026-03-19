import streamlit as st
from openai import OpenAI

from utils.sensitive_data import get_api_key


def main():
    # 初始化 OpenAI 客户端（完全保留原有配置）
    client = OpenAI(
        api_key=get_api_key(),
        base_url="https://api.deepseek.com/v1",  # deepseek 接口地址
    )

    # 初始化对话历史（保留原有逻辑）
    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.title("🤖 AI 助手")
    # 恢复标签可见性，避免用户看不懂选项含义，同时增加宽度
    model = st.selectbox("选择模型", ['deepseek-chat', "gpt-3.5-turbo", "gpt-4"], index=0)
    # 调整滑块宽度，恢复标签
    temperature = st.slider("生成温度", 0.0, 1.0, 0.7, step=0.1)
    if st.button("清空对话历史", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.rerun()  # 清空后刷新页面

    # ========== 核心：聊天区域（优化高度和间距，解决拥挤） ==========
    # 调整聊天容器高度，避免过高导致拥挤，同时保留滚动
    chat_container = st.container(height=500, border=True)  # 高度从600调整为500，更适配侧边栏

    with chat_container:
        # 显示历史对话（保留原有逻辑，仅增加消息间距）
        for idx, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"], avatar="👤" if message["role"] == "user" else "🤖"):
                st.markdown(f"{message['content']}")
            # 增加消息之间的间距，避免挤在一起
            st.markdown("<br>", unsafe_allow_html=True)

    # ========== 底部固定输入框（保留原有逻辑，优化间距） ==========
    input_placeholder = st.empty()
    with input_placeholder:
        # 输入框增加宽度，避免拥挤
        prompt = st.chat_input("请输入你的问题...", key="chat_input")

    # ========== 处理用户输入（完全保留原有逻辑） ==========
    if prompt:
        # 添加用户消息到历史
        st.session_state.messages.append({"role": "user", "content": prompt})

        # 实时更新聊天区域（添加用户消息）
        with chat_container:
            with st.chat_message(message["role"], avatar="👤"):
                st.markdown(prompt)
            st.markdown("<br>", unsafe_allow_html=True)

        # 调用AI生成响应（流式输出）
        with chat_container:
            with st.chat_message("assistant", avatar="🤖"):
                message_placeholder = st.empty()
                full_response = ""

                # 调用DeepSeek/OpenAI API（完全保留原有配置）
                stream = client.chat.completions.create(
                    model=model,
                    messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                    temperature=temperature,
                    stream=True
                )

                # 流式输出（模拟打字效果）
                for chunk in stream:
                    chunk_content = chunk.choices[0].delta.content or ""
                    full_response += chunk_content
                    message_placeholder.markdown(full_response + "▌")

                # 最终显示完整响应（移除光标）
                message_placeholder.markdown(full_response)
            st.markdown("<br>", unsafe_allow_html=True)

        # 将AI响应添加到历史
        st.session_state.messages.append({"role": "assistant", "content": full_response})

        # 刷新页面确保输入框保持在底部
        st.rerun()


if __name__ == "__main__":
    main()