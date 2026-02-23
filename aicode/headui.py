import numpy as np
import streamlit as st
import plotly.express as px
from matplotlib import pyplot as plt
from plotly.data import tips


def main():
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
