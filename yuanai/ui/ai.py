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


# ==================== 核心交互函数 ====================
async def chat_with_agent_stream(
        llm,
        prompt: str,
        images_base64: List[str],
        tools: List[Any],
        history: List[BaseMessage],
        system_message: SystemMessage,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    与 LangGraph Agent 交互，以流式事件的形式返回结果。
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
        yield {"type": "done", "data": full_response}
    except Exception as e:
        yield {"type": "error", "data": str(e)}


# ==================== 工具函数 ====================
def parse_session_message(msg) -> tuple:
    """解析 session_state 中的消息元组，兼容新旧格式"""
    if len(msg) == 2:
        role, content = msg
        images = []
    elif len(msg) == 3:
        role, content, images = msg
        if images is None:
            images = []
        elif isinstance(images, str):
            images = [images]
    else:
        role, content, images = msg
    return role, content, images


def process_uploaded_images(uploaded_files) -> List[str]:
    """将上传的文件列表转换为 base64 data URL 列表"""
    images_base64 = []
    if not uploaded_files:
        return images_base64

    for file in uploaded_files:
        try:
            bytes_data = file.getvalue()
            base64_image = base64.b64encode(bytes_data).decode('utf-8')
            mime_type = file.type
            img_url = f"data:{mime_type};base64,{base64_image}"
            images_base64.append(img_url)
        except Exception as e:
            st.error(f"图片处理失败: {file.name} - {str(e)}")
    return images_base64


def display_message(container, role: str, content: str, images: List[str], avatar=None):
    """在 Streamlit 容器中显示单条聊天消息"""
    with container.chat_message(role, avatar=avatar):
        st.markdown(content)
        if images:
            cols = st.columns(len(images))
            for idx, img in enumerate(images):
                with cols[idx]:
                    st.image(img, width=150)


def display_image_preview(uploaded_files):
    """在输入区域显示上传图片的预览（可选，若不需要可删除）"""
    if not uploaded_files:
        return

    st.write(f"已选择 {len(uploaded_files)} 张图片")
    preview_cols = st.columns(min(len(uploaded_files), 4))
    for idx, file in enumerate(uploaded_files[:4]):
        with preview_cols[idx % 4]:
            try:
                st.image(file, width=80, caption=f"图片{idx + 1}")
            except Exception as e:
                st.error(f"预览失败: {str(e)}")
    if len(uploaded_files) > 4:
        st.caption(f"还有 {len(uploaded_files) - 4} 张未显示")


async def execute_chat_stream(
        llm,
        prompt: str,
        images_base64: List[str],
        tools: List[Any],
        history: List[BaseMessage],
        system_message: SystemMessage,
        message_placeholder
):
    """执行流式聊天交互，更新 UI 并返回完整响应"""
    full_response = ""
    async for event in chat_with_agent_stream(
            prompt=prompt,
            images_base64=images_base64,
            llm=llm,
            tools=tools,
            history=history,
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


def get_chat_history() -> List[BaseMessage]:
    """构建对话历史，忽略图片（仅文本）"""
    chat_history = []
    for msg in st.session_state.messages:
        role, content, _ = parse_session_message(msg)
        if role == "user":
            chat_history.append(HumanMessage(content=content))
        elif role == "assistant":
            chat_history.append(AIMessage(content=content))
    return chat_history


def load_css():
    """加载自定义 CSS 样式"""
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


# ==================== 主程序 ====================
def main():
    initializing_state(INITIAL_STATE)
    load_css()

    col1, col2 = st.columns([3, 1])

    # 模型选择与配置
    llm = get_llm(
        col2.selectbox("选择模型",
                       ['deepseek-chat', "doubao-seed-2-0-pro-260215", 'doubao-seed-2-0-lite-260215', "deepseek-coder"],
                       index=0),
        temperature=col2.slider("生成温度", 0.0, 1.0, 0.7, step=0.1),
        verbose=False,
        streaming=True
    )

    # 清空历史按钮
    if col2.button("清空对话历史", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    # 聊天容器
    chat_container = col1.container(height=500, border=True)
    with chat_container:
        for msg in st.session_state.messages:
            role, content, images = parse_session_message(msg)
            avatar = "👤" if role == "user" else os.path.join(root_path(), "data/file/img/home.ico")
            display_message(chat_container, role, content, images, avatar)

    # 输入区域（仅保留 chat_input，自带多文件上传）
    latest_prompt = st.chat_input(
        "请输入你的问题（支持工具调用 + 多图上传）...",
        key="chat_input",
        accept_file="multiple",  # 👈 关键：允许多文件
        file_type=["jpg", "jpeg", "png"]  # 👈 限制图片类型
    )

    # 处理用户输入（文本 + 文件统一从 latest_prompt 获取）
    if latest_prompt:
        # 1. 分离文本和文件
        user_text = latest_prompt.text or ""
        uploaded_files = latest_prompt.files  # 👈 从 chat_input 拿文件

        # 2. 处理图片文件（转 base64）
        images_base64 = process_uploaded_images(uploaded_files)

        # 3. 保存并显示用户消息
        st.session_state.messages.append(("user", user_text, images_base64))
        with chat_container:
            display_message(chat_container, "user", user_text, images_base64, "👤")

        # 4. 调用 Agent 生成回复
        tools = in_tools
        system_message = SystemMessage(content="你是一个能调用工具的助手")
        chat_history = get_chat_history()

        with chat_container:
            avatar = os.path.join(root_path(), "data/file/img/home.ico")
            with chat_container.chat_message("assistant", avatar=avatar):
                message_placeholder = st.empty()
                message_placeholder.markdown(
                    '<div style="display: flex; align-items: center;"><div class="loader"></div><span '
                    'style="margin-left: 8px;">正在分析...</span></div>',
                    unsafe_allow_html=True
                )

                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    full_response = loop.run_until_complete(
                        execute_chat_stream(
                            llm=llm,
                            prompt=user_text,  # 👈 传文本
                            images_base64=images_base64,  # 👈 传图片
                            tools=tools,
                            history=chat_history,
                            system_message=system_message,
                            message_placeholder=message_placeholder
                        )
                    )
                except Exception as e:
                    full_response = f"请求出错：{str(e)}"
                    message_placeholder.markdown(full_response)

        # 5. 保存助手回复
        if full_response:
            st.session_state.messages.append(("assistant", full_response, []))

        st.rerun()


if __name__ == "__main__":
    main()
