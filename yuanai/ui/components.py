import streamlit as st
from typing import List


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
    """在输入区域显示上传图片的预览"""
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


def show_loading_indicator(placeholder):
    """显示加载动画"""
    placeholder.markdown(
        '<div style="display: flex; align-items: center;"><div class="loader"></div><span style="margin-left: 8px;">正在分析...</span></div>',
        unsafe_allow_html=True
    )


def show_error(placeholder, message: str):
    """显示错误信息"""
    placeholder.markdown(message)


def show_tool_status(event_type: str, tool_name: str):
    """显示工具调用状态"""
    if event_type == "tool_start":
        st.info(f"🔧 正在调用工具: {tool_name}")
    elif event_type == "tool_end":
        st.success(f"✅ 工具调用完成: {tool_name}")