import streamlit as st
from playwright.sync_api import sync_playwright, Playwright

# 项目内置模块
from spiderlx.auto.web.playwrightdo.main import init_playwright_browser, able_web
from utils.app_core import initializing_state, reset_to_initial
from spiderlx.ui import uixiaoyuan

# -------------------------- 1. 初始化状态（新增context，适配函数返回值） --------------------------
# 所有状态变量前缀为pw_，新增pw_context存储上下文实例（核心适配点）
PW_INITIAL_STATE = {
    "pw_step": 1,  # Playwright步骤
    "pw_playwright": None,  # Playwright核心实例（新增）
    "pw_browser": None,  # 浏览器实例
    "pw_context": None,  # 上下文实例（适配函数返回值）
    "pw_page": None,  # 页面实例
    "pw_browser_started": False,  # 浏览器启动状态
    "pw_url": "",  # 目标URL
    "pw_web_name": "",  # 选中的网站名称
    "pw_web_open": False  # 网站是否已打开
}


# -------------------------- 2. 核心函数（完全适配init_playwright_browser） --------------------------
def get_pw_driver(headless=False):
    """
    获取Playwright驱动（适配init_playwright_browser的返回值）
    :param headless: 是否无头模式
    :return: playwright, browser, context, page | None, None, None, None
    """
    try:
        # 1. 启动Playwright核心实例
        playwright = sync_playwright().start()
        # 2. 调用项目内置函数，传入playwright实例，获取浏览器/上下文/页面
        browser, context, page = init_playwright_browser(p=playwright, headless=headless)
        return playwright, browser, context, page
    except Exception as e:
        st.error(f"Playwright浏览器初始化失败：{str(e)}")
        return None, None, None, None


def show_pw_state():
    """展示Playwright运行状态"""
    st.write('Playwright开启状态', st.session_state.pw_browser_started)


def get_able_web():
    """获取可访问的网站列表（保留原有逻辑）"""
    return able_web()


def open_pw_web(page, web_info, web_name):
    """
    打开指定网站（简化参数，context/page已由init_playwright_browser初始化）
    :param page: Playwright页面实例
    :param web_info: 网站信息字典
    :param web_name: 选中的网站名
    :return: 成功返回web_name，失败返回空字符串
    """
    # 反转字典：网站名 → URL
    web_url_map = {v: k for k, v in web_info.items()}
    url = web_url_map.get(web_name, "")

    if not url:
        st.error(f"未找到「{web_name}」对应的URL！")
        return ""

    try:
        # 使用预初始化的page访问URL（反检测配置已在context中完成）
        page.goto(url, wait_until="networkidle", timeout=30000)
        return web_name
    except Exception as e:
        st.error(f"打开「{web_name}」失败：{str(e)}")
        return ""


# -------------------------- 3. 资源清理函数（适配context/浏览器/playwright） --------------------------
def cleanup_pw_resources():
    """安全清理Playwright所有资源（上下文→页面→浏览器→playwright）"""
    try:
        # 1. 关闭页面
        if st.session_state.pw_page:
            st.session_state.pw_page.close()
        # 2. 关闭上下文（核心：Cookie/环境隔离的上下文必须关闭）
        if st.session_state.pw_context:
            st.session_state.pw_context.close()
        # 3. 关闭浏览器
        if st.session_state.pw_browser:
            st.session_state.pw_browser.close()
        # 4. 停止Playwright核心实例
        if st.session_state.pw_playwright:
            st.session_state.pw_playwright.stop()
        # 5. 重置状态
        reset_to_initial(PW_INITIAL_STATE)
        st.success("Playwright资源已全部清理！")
    except Exception as e:
        st.error(f"清理Playwright资源失败：{str(e)}")


# -------------------------- 4. 主应用逻辑 --------------------------
def app_main():
    # 初始化状态（确保每次运行都有基础状态）
    initializing_state(PW_INITIAL_STATE)

    with st.sidebar.container(border=True):
        col1, col2, col3 = st.columns(3)

        # 1. 浏览器启停按钮（核心适配init_playwright_browser的返回值）
        with col1:
            if not st.session_state.pw_browser_started:
                if st.button('开启Playwright浏览器', type='primary', use_container_width=True):
                    # 获取playwright+浏览器+上下文+页面（调试用headless=False）
                    playwright, browser, context, page = get_pw_driver(headless=False)
                    # 校验核心实例是否有效
                    if all([playwright, browser, context, page]):
                        # 存储所有实例到session_state
                        st.session_state.pw_playwright = playwright
                        st.session_state.pw_browser = browser
                        st.session_state.pw_context = context
                        st.session_state.pw_page = page
                        st.session_state.pw_browser_started = True
                        st.session_state.app_home = False
                        st.rerun()
                    else:
                        st.warning("浏览器启动失败！请检查Chrome是否安装/Playwright驱动是否正常。")
            else:
                if st.button('关闭Playwright浏览器', use_container_width=True):
                    cleanup_pw_resources()
                    st.session_state.pw_browser_started = False
                    st.rerun()

        # 2. 展示状态
        with col2:
            show_pw_state()

        # 3. 返回上一步
        with col3:
            if st.button('返回Playwright上一步', use_container_width=True) and st.session_state.pw_step > 1:
                st.session_state.pw_step -= 1
                st.rerun()

    # -------------------------- 步骤1：选择并打开网站 --------------------------
    if st.session_state.pw_step == 1 and st.session_state.pw_browser_started:
        st.subheader(f'Playwright第{st.session_state.pw_step}步：选择目标网站')
        web_info = get_able_web()

        if web_info:
            # 选择网站（存储到pw_web_name）
            st.session_state.pw_web_name = st.selectbox(
                '请选择想要访问的网站',
                options=list(web_info.values()),
                key="pw_web_selector",
                disabled=not st.session_state.pw_browser_started
            )
            st.write('即将进入：', st.session_state.pw_web_name)

            if st.button('Playwright打开网站', disabled=not st.session_state.pw_web_name):
                with st.spinner(f"正在打开「{st.session_state.pw_web_name}」..."):
                    # 使用预初始化的page打开网站
                    name = open_pw_web(
                        page=st.session_state.pw_page,
                        web_info=web_info,
                        web_name=st.session_state.pw_web_name
                    )
                    if name:
                        st.success(f'「{name}」已成功打开！')
                        st.session_state.pw_web_open = True
                        st.session_state.pw_step = 2
                        st.rerun()
        else:
            st.warning("暂无可用的网站列表！")

    # -------------------------- 步骤2：网站自动化解析 --------------------------
    if st.session_state.pw_step == 2 and st.session_state.pw_browser_started:
        with st.sidebar.container(border=True):
            st.subheader(f'Playwright第{st.session_state.pw_step}步：{st.session_state.pw_web_name} 自动化解析')

        if st.session_state.pw_web_name == '小猿众包':
            # 传入预初始化的page到小猿众包自动化模块
            # uixiaoyuan.main(page=st.session_state.pw_page)
            st.warning('小猿众包自动化模块待开发（已传入Playwright Page实例）')
        elif not st.session_state.pw_web_name:
            st.info("请先选择并打开目标网站！")
        else:
            st.write(f'「{st.session_state.pw_web_name}」自动化模块待开发~~~')

    # -------------------------- 步骤3：预留扩展 --------------------------
    if st.session_state.pw_step == 3 and st.session_state.pw_browser_started:
        st.subheader(f'Playwright第{st.session_state.pw_step}步：预留扩展')


# -------------------------- 5. 程序入口 --------------------------
if __name__ == '__main__':
    # 测试获取网站列表（可选）
    try:
        info = get_able_web()
        print("可用网站列表：", list(info.values()))
    except Exception as e:
        print("获取网站列表失败：", str(e))

    # 启动Streamlit应用
    app_main()