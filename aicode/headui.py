import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

# --------------------------
# 1. 页面基础配置 (必须放在最前面)
# --------------------------
st.set_page_config(
    page_title="数据可视化 Dashboard",
    page_icon="📊",
    layout="wide",  # 宽屏布局
    initial_sidebar_state="expanded"  # 侧边栏默认展开
)


# --------------------------
# 2. 自定义 CSS 美化样式（含顶部导航）
# --------------------------
def local_css():
    st.markdown("""
    <style>
    /* 全局样式 */
    .main {
        padding: 2rem 1rem;
    }

    /* 顶部导航栏核心样式（横向头部） */
    .top-nav {
        background-color: #f8f9fa;
        padding: 10px 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        display: flex;
        gap: 10px;
        align-items: center;
    }
    .top-nav .nav-btn {
        flex: 1;
    }

    /* 卡片样式 */
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 0.5rem;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    /* 标题样式 */
    .title-text {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1e3a8a;
        margin-bottom: 0.5rem;
    }

    /* 副标题样式 */
    .subtitle-text {
        font-size: 1.1rem;
        color: #64748b;
        margin-bottom: 2rem;
    }

    /* 页脚样式 */
    .footer {
        text-align: center;
        padding: 2rem 0;
        color: #64748b;
        font-size: 0.9rem;
    }

    /* 调整侧边栏间距 */
    [data-testid="stSidebar"] {
        padding-top: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)


local_css()


# --------------------------
# 3. 生成示例数据（复用原有函数）
# --------------------------
def generate_sample_data():
    """生成用于展示的示例数据"""
    # 日期范围
    dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
    n_days = len(dates)

    # 生成数据
    data = pd.DataFrame({
        '日期': dates,
        '销售额': np.random.randint(5000, 20000, size=n_days) + np.linspace(0, 5000, n_days),
        '订单量': np.random.randint(100, 500, size=n_days),
        '客单价': np.round(np.random.uniform(80, 150, size=n_days), 2),
        '地区': np.random.choice(['华东', '华北', '华南', '西南', '西北'], size=n_days)
    })

    # 计算汇总指标
    total_sales = data['销售额'].sum()
    avg_order = data['订单量'].mean()
    avg_price = data['客单价'].mean()
    growth_rate = np.round((data['销售额'].iloc[-1] - data['销售额'].iloc[0]) / data['销售额'].iloc[0] * 100, 2)

    return data, total_sales, avg_order, avg_price, growth_rate


# --------------------------
# 4. 渲染顶部导航栏（合并后仅保留3个导航项）
# --------------------------
def render_top_navbar():
    """渲染真正的顶部横向导航栏"""
    # 初始化页面状态（首次加载默认显示数据看板）
    if "active_page" not in st.session_state:
        st.session_state.active_page = "数据看板"

    # 渲染导航栏容器
    st.markdown("<div class='top-nav'>", unsafe_allow_html=True)

    # 导航按钮（合并后只保留：数据看板、数据明细、关于系统）
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📊 数据看板", use_container_width=True, key="nav_dashboard", help="核心指标+趋势分析"):
            st.session_state.active_page = "数据看板"
    with col2:
        if st.button("📋 数据明细", use_container_width=True, key="nav_detail", help="完整数据列表"):
            st.session_state.active_page = "数据明细"
    with col3:
        if st.button("ℹ️ 关于系统", use_container_width=True, key="nav_about", help="系统介绍"):
            st.session_state.active_page = "关于系统"

    # 闭合导航栏容器
    st.markdown("</div>", unsafe_allow_html=True)


# --------------------------
# 5. 渲染不同页面内容（核心：数据看板合并指标+趋势）
# --------------------------
def render_page_content(df, total_sales, avg_order, avg_price, growth_rate):
    """根据激活的导航页渲染对应内容"""
    active_page = st.session_state.active_page

    if active_page == "数据看板":
        # 合并后的数据看板页面：核心指标 + 趋势分析
        st.markdown('<p class="title-text">📊 数据看板</p>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle-text">核心业务指标 + 多维度趋势分析</p>', unsafe_allow_html=True)

        # 第一部分：核心指标卡片
        st.subheader("📈 核心业务指标")
        card1, card2, card3, card4 = st.columns(4)
        with card1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("总销售额", f"¥{total_sales:,.0f}", f"{growth_rate:+.2f}%")
            st.markdown('</div>', unsafe_allow_html=True)
        with card2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("日均订单量", f"{avg_order:.0f}", "+8.5%")
            st.markdown('</div>', unsafe_allow_html=True)
        with card3:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("平均客单价", f"¥{avg_price:.2f}", "-1.2%")
            st.markdown('</div>', unsafe_allow_html=True)
        with card4:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("数据覆盖天数", f"{len(df)} 天", "稳定")
            st.markdown('</div>', unsafe_allow_html=True)

        # 第二部分：趋势分析图表（原趋势分析页面内容）
        st.subheader("📊 数据趋势分析")
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            fig1 = px.line(df, x='日期', y='销售额', title='销售额日趋势', color_discrete_sequence=['#1e3a8a'])
            fig1.update_layout(height=400)
            st.plotly_chart(fig1, use_container_width=True)
        with chart_col2:
            region_sales = df.groupby('地区')['销售额'].sum().reset_index()
            fig2 = px.pie(region_sales, values='销售额', names='地区', title='各地区销售额占比')
            fig2.update_layout(height=400)
            st.plotly_chart(fig2, use_container_width=True)

    elif active_page == "数据明细":
        # 数据明细页面（保留原有逻辑）
        st.markdown('<p class="title-text">📋 数据明细</p>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle-text">完整业务数据明细查询与导出</p>', unsafe_allow_html=True)

        # 数据下载
        csv_data = df.to_csv(index=False).encode('utf-8')
        col1, col2 = st.columns([8, 2])
        with col2:
            st.download_button(
                label="📥 下载数据 (CSV)",
                data=csv_data,
                file_name=f"业务数据_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                key="download_csv"
            )
        # 数据表格
        st.dataframe(df, use_container_width=True, hide_index=True)

    elif active_page == "关于系统":
        # 关于系统页面（保留原有逻辑）
        st.markdown('<p class="title-text">ℹ️ 关于系统</p>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle-text">业务数据可视化 Dashboard 介绍</p>', unsafe_allow_html=True)

        st.info("""
        ### 📋 系统说明
        - 基于 Streamlit 构建的轻量化数据可视化工具
        - 支持核心业务指标监控、趋势分析、数据导出
        - 适配宽屏布局，支持侧边栏筛选与顶部导航切换

        ### 🛠️ 技术栈
        - 前端：Streamlit + Plotly + CSS
        - 数据处理：Pandas + NumPy
        """)


# --------------------------
# 6. 主函数（核心执行逻辑）
# --------------------------
def main():
    # 1. 生成示例数据
    df, total_sales, avg_order, avg_price, growth_rate = generate_sample_data()

    # 2. 渲染顶部导航栏（合并后仅3个导航项）
    render_top_navbar()

    # 3. 渲染侧边栏（完全保留原有逻辑）
    with st.sidebar:
        st.header("🔍 数据筛选")

        # 日期筛选
        date_range = st.date_input(
            "选择日期范围",
            value=[df['日期'].min(), df['日期'].max()],
            min_value=df['日期'].min(),
            max_value=df['日期'].max(),
            key="date_range"
        )

        # 地区筛选
        regions = st.multiselect(
            "选择地区",
            options=df['地区'].unique(),
            default=df['地区'].unique(),
            key="region_select"
        )

        # 数据刷新按钮
        if st.button("🔄 刷新数据", type="primary", key="refresh_btn"):
            df, total_sales, avg_order, avg_price, growth_rate = generate_sample_data()
            st.success("数据已刷新！")

        # 侧边栏分割线 + 说明
        st.divider()
        st.info("""
        ### 📌 操作说明
        - 顶部导航切换不同页面
        - 筛选条件实时生效
        - 支持数据导出为CSV格式
        """)

    # 4. 根据顶部导航渲染对应页面内容
    render_page_content(df, total_sales, avg_order, avg_price, growth_rate)

    # 5. 渲染页脚
    st.markdown("---")
    st.markdown('<div class="footer">© 2025 数据可视化 Dashboard | 基于 Streamlit 构建</div>', unsafe_allow_html=True)


# --------------------------
# 7. 程序入口（标准写法）
# --------------------------
if __name__ == "__main__":
    main()