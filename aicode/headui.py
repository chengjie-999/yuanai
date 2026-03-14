import numpy as np
import streamlit as st
import plotly.express as px
from matplotlib import pyplot as plt
from plotly.data import tips


def ti():
    pass


def main():
    t0()


def t0():
    # 自定义CSS：放大标签页样式（核心）
    st.markdown("""
        <style>
        /* 调整标签页整体样式 */
        div[data-baseweb="tab-list"] {
            gap: 0.5rem;  /* 标签之间的间距 */
            padding: 1rem 0;  /* 上下内边距 */
        }
        /* 调整标签按钮样式 */
        button[data-baseweb="tab"] {
            font-size: 1.2rem !important;  /* 字体大小（放大） */
            padding: 1rem 2rem !important;  /* 内边距（按钮更大） */
            border-radius: 8px !important;  /* 圆角更柔和 */
            font-weight: 600 !important;  /* 字体加粗 */
        }
        /* 选中标签的样式 */
        button[data-baseweb="tab"][aria-selected="true"] {
            background-color: #1f77b4 !important;  /* 选中标签的背景色 */
            color: white !important;
        }
        </style>
        """, unsafe_allow_html=True)

    # 放大后的标签页（适合首页导航）
    tab1, tab2, tab3 = st.tabs(["📈 数据看板", "🔍 数据查询", "⚙️ 系统设置"])

    # 标签页内容（首页级别的布局）
    with tab1:
        st.header("数据看板（首页核心模块）")
        st.write("这里放置首页核心的可视化图表、关键指标等内容")
        # 示例：首页关键指标卡片
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("今日销售额", "¥12.5万", "+2.3万")
        with col2:
            st.metric("今日订单数", "890单", "+120单")
        with col3:
            st.metric("用户留存率", "78.5%", "-1.2%")

    with tab2:
        st.header("数据查询模块")
        st.write("这里放置数据筛选、查询、导出等功能")

    with tab3:
        st.header("⚙️系统设置模块")
        st.write("这里放置用户设置、权限管理等功能")
    # 1. 定义标签页名称，创建标签页对象
    tab1, tab2, tab3 = st.tabs(["首页", "数据展示", "可视化"])

    # 2. 为第一个标签页（首页）添加内容
    with tab1:
        # 基础单选按钮组：label是显示的标题，options是选项列表
        selected_option = st.radio(
            label="请选择你喜欢的水果：",  # 单选组的标题
            options=["苹果", "香蕉", "橙子", "葡萄"]  # 可选值列表
        )

        # 展示用户选中的结果
        st.write(f"你选择的水果是：{selected_option}")

    # 3. 为第二个标签页（数据展示）添加内容
    with tab2:
        st.subheader("数据表格展示")
        import pandas as pd
        # 模拟数据
        data = pd.DataFrame({
            "姓名": ["张三", "李四", "王五"],
            "年龄": [25, 30, 28],
            "薪资": [8000, 10000, 9000]
        })
        st.dataframe(data, use_container_width=True)

    # 4. 为第三个标签页（可视化）添加内容
    with tab3:
        st.subheader("柱状图可视化")
        # 基于上面的数据绘制柱状图
        st.bar_chart(data.set_index("姓名")["薪资"])
        st.write("这是第三个标签页的可视化内容～")

    # 运行方式：终端执行 streamlit run 你的文件名.py
    # 接上面的代码继续添加
    st.subheader("Plotly 交互式图表")

    # Plotly 绘图（和 Jupyter 中一样）
    fig3 = px.scatter(tips(), x="total_bill", y="tip", color="day",
                      size="size", hover_data=["time"],
                      title="消费金额 vs 小费（按星期区分）")

    # Streamlit 展示 Plotly 图表
    st.plotly_chart(fig3, use_container_width=True)  # use_container_width 自适应宽度

    # 设置页面标题 -------------------------------------------------------------------------------------------
    st.title("Streamlit 展示 Matplotlib 图表")
    plt.rcParams['font.sans-serif'] = 'SimHei'
    plt.rcParams['axes.unicode_minus'] = False

    # 准备数据（可结合Streamlit控件动态调整）
    x = np.linspace(0, 10, 100)
    # 添加滑块控件，动态调整振幅
    amplitude = st.slider("调整正弦曲线振幅", 1, 10, 2)
    y = amplitude * np.sin(x)

    # 创建图表（注意：Streamlit中建议用plt.subplots()方式创建fig）
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(x, y, label=f"sin(x) × {amplitude}", color="red")
    ax.set_title("动态调整的正弦曲线")
    ax.set_xlabel("X轴")
    ax.set_ylabel("Y轴")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Streamlit渲染Matplotlib图表（核心步骤）
    st.pyplot(fig)  # 直接传入fig对象即可渲染
