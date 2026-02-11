import streamlit as st


def ai_code_test():
    # 标题
    st.write("st.multiselect() 基础示例")

    # 创建多选下拉框
    selected_fruits = st.multiselect(
        label="请选择你喜欢的水果：",  # 必选标签
        options=["苹果", "香蕉", "橙子", "草莓", "葡萄"],  # 可选选项
        default=["苹果", "草莓"],  # 默认选中的选项
        placeholder="选择1个或多个水果"  # 未选择时的提示
    )

    # 展示选择结果
    st.write("你选中的水果是：", selected_fruits)


def main():
    ai_code_test()
