import streamlit as st


def main():
    # 初始化持久化状态（优先从localStorage读取，无则初始化）
    if "counter" not in st.experimental_user_state:
        st.experimental_user_state.counter = 0

    # 交互逻辑
    st.write(f"当前计数：{st.experimental_user_state.counter}")
    if st.button("增加"):
        st.experimental_user_state.counter += 1
        st.rerun()  # 刷新页面更新显示

    # 清除状态（可选）
    if st.button("重置"):
        del st.experimental_user_state.counter
        st.rerun()
