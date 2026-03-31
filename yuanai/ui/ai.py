import os
import asyncio
import base64
import time
import streamlit as st

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from typing import List, AsyncGenerator, Dict, Any

from yuanai.core.lc import get_llm, get_langgraph_agent
from yuanai.tools import all_tools as in_tools
from webui.app_core import initializing_state
from utils.data_path import root_path

INITIAL_STATE = {"messages": []}


# ==================== 独立封装函数 ====================
async def chat_with_agent_stream(
    prompt: str,
    images_base64: List[str],
    llm,
    tools: List[Any],
    history: List[BaseMessage],
    system_message: SystemMessage,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    与 LangGraph Agent 交互，以流式事件的形式返回结果。

    Args:
        prompt: 用户输入的文本提示词
        images_base64: 图片的 base64 data URL 列表（例如 ["data:image/jpeg;base64,..."]）
        llm: 已初始化的 LLM 实例
        tools: 工具列表
        history: 历史消息列表（LangChain BaseMessage 对象）
        system_message: 系统消息

    Yields:
        字典，包含以下类型的事件：
        - type: "token", data: 文本片段
        - type: "tool_start", data: {"name": 工具名}
        - type: "tool_end", data: {"name": 工具名}
        - type: "error", data: 错误信息
        - type: "done", data: 完整响应文本
    """
    # 构建多模态用户消息
    if images_base64:
        user_content = [{"type": "text", "text": prompt}]
        for img_url in images_base64:
            user_content.append({"type": "image_url", "image_url": {"url": img_url}})
        human_message = HumanMessage(content=user_content)
    else:
        human_message = HumanMessage(content=prompt)

    # 组装消息列表
    input_messages = [system_message] + history + [human_message]

    # 创建 agent
    agent = get_langgraph_agent(llm, tools)

    full_response = ""
    try:
        async for event in agent.astream_events(
            {"messages": input_messages},
            version="v2"
        ):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                if token:
                    full_response += token
                    yield {"type": "token", "data": token}
            elif event["event"] == "on_tool_start":
                yield {"type": "tool_start", "data": {"name": event["name"]}}
            elif event["event"] == "on_tool_end":
                yield {"type": "tool_end", "data": {"name": event["name"]}}
        # 流式结束后返回完整响应
        yield {"type": "done", "data": full_response}
    except Exception as e:
        yield {"type": "error", "data": str(e)}


# ==================== Streamlit 界面部分 ====================
def get_chat_history():
    """构建对话历史，忽略图片（仅文本）"""
    chat_history = []
    for msg in st.session_state.messages:
        role, content = msg[0], msg[1]  # 只取角色和文本
        if role == "user":
            chat_history.append(HumanMessage(content=content))
        elif role == "assistant":
            chat_history.append(AIMessage(content=content))
    return chat_history


def main():
    initializing_state(INITIAL_STATE)

    # 初始化动态 key，用于图片上传组件
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = str(time.time())

    # 添加加载动画 CSS
    st.markdown("""
    <style>
    .loader {
        border: 2px solid #f3f3f3;
        border-top: 2px solid #3498db;
        border-radius: 50%;
        width: 16px;
        height: 16px;
        animation: spin 1s linear infinite;
        display: inline-block;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    </style>
    """, unsafe_allow_html=True)

    st.write("🤖 小元AI助手")
    col1, col2 = st.columns([3, 1])

    llm = get_llm(
        col2.selectbox("选择模型",
                       ['deepseek-chat', "doubao-seed-2-0-pro-260215", 'doubao-seed-2-0-lite-260215', "deepseek-coder"],
                       index=0),
        temperature=col2.slider("生成温度", 0.0, 1.0, 0.7, step=0.1),
        verbose=False,
        streaming=True
    )

    if col2.button("清空对话历史", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    chat_container = col1.container(height=500, border=True)
    with chat_container:
        for msg in st.session_state.messages:
            # 兼容旧格式（2元素无图，3元素单图）和新格式（4元素多图）
            if len(msg) == 2:
                role, content = msg
                images = []
            elif len(msg) == 3:
                role, content, images = msg
                if images is None:
                    images = []
                elif isinstance(images, str):
                    images = [images]  # 兼容旧单图存储
            else:
                role, content, images = msg

            with st.chat_message(
                    role,
                    avatar="👤" if role == "user" else os.path.join(root_path(), "data/file/img/home.ico")
            ):
                st.markdown(content)
                if images:
                    # 显示多张图片，每张宽度 150px
                    cols = st.columns(len(images))
                    for idx, img in enumerate(images):
                        with cols[idx]:
                            st.image(img, width=150)

    # ========== 输入区域：聊天框在上，图片上传在下 ==========
    input_container = st.sidebar.container()
    # input_container = col1.container()
    with input_container:
        # 1. 聊天输入框
        latest_prompt = st.chat_input("请输入你的问题（支持工具调用）...", key="chat_input")

        # 2. 多图片上传组件（使用动态 key）
        uploaded_files = st.file_uploader(
            "📷 上传图片（可选，支持多张）",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,  # 允许多选
            key=st.session_state.uploader_key,
            label_visibility="visible"
        )

        # 3. 图片预览（在上传组件下方）
        if uploaded_files:
            st.write(f"已选择 {len(uploaded_files)} 张图片")
            preview_cols = st.columns(min(len(uploaded_files), 4))  # 最多4列预览
            for idx, file in enumerate(uploaded_files[:4]):
                with preview_cols[idx % 4]:
                    try:
                        st.image(file, width=80, caption=f"图片{idx+1}")
                    except Exception as e:
                        st.error(f"预览失败: {str(e)}")
            if len(uploaded_files) > 4:
                st.caption(f"还有 {len(uploaded_files)-4} 张未显示")

    if latest_prompt:
        # 处理多张图片
        images_base64 = []
        if uploaded_files:
            for file in uploaded_files:
                try:
                    bytes_data = file.getvalue()
                    base64_image = base64.b64encode(bytes_data).decode('utf-8')
                    mime_type = file.type
                    img_url = f"data:{mime_type};base64,{base64_image}"
                    images_base64.append(img_url)
                except Exception as e:
                    st.error(f"图片处理失败: {file.name} - {str(e)}")

        # 保存用户消息（包含文本和多张图片）
        st.session_state.messages.append(("user", latest_prompt, images_base64))

        # 显示用户消息（立即显示）
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(latest_prompt)
                if images_base64:
                    cols = st.columns(len(images_base64))
                    for idx, img in enumerate(images_base64):
                        with cols[idx]:
                            st.image(img, width=150)

        # 准备模型交互所需参数
        tools = in_tools
        system_message = SystemMessage(content="你是一个能调用工具的助手")
        chat_history = get_chat_history()

        # 在 Streamlit 中运行异步交互
        async def run_chat():
            full_response = ""
            async for event in chat_with_agent_stream(
                prompt=latest_prompt,
                images_base64=images_base64,
                llm=llm,
                tools=tools,
                history=chat_history,
                system_message=system_message
            ):
                if event["type"] == "token":
                    full_response += event["data"]
                    message_placeholder.markdown(full_response + "▌")
                elif event["type"] == "tool_start":
                    st.info(f"🔧 正在调用工具: {event['data']['name']}")
                elif event["type"] == "tool_end":
                    st.success(f"✅ 工具调用完成: {event['data']['name']}")
                elif event["type"] == "error":
                    full_response = event["data"]
                    message_placeholder.markdown(full_response)
                elif event["type"] == "done":
                    full_response = event["data"]
                    message_placeholder.markdown(full_response)
            return full_response

        with chat_container:
            with st.chat_message(
                    "assistant",
                    avatar=os.path.join(root_path(), "data/file/img/home.ico")
            ):
                message_placeholder = st.empty()
                # 动态加载提示
                message_placeholder.markdown(
                    '<div style="display: flex; align-items: center;"><div class="loader"></div><span '
                    'style="margin-left: 8px;">正在分析...</span></div>',
                    unsafe_allow_html=True
                )
                # 运行异步函数
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    full_response = loop.run_until_complete(run_chat())
                except Exception as e:
                    full_response = f"请求出错：{str(e)}"
                    message_placeholder.markdown(full_response)

        if full_response:
            st.session_state.messages.append(("assistant", full_response, []))

        # 清除图片上传状态：更新动态 key，让 file_uploader 重置
        st.session_state.uploader_key = str(time.time())
        st.rerun()


if __name__ == "__main__":
    main()