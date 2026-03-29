import streamlit as st

from spiderlx.ui.selenium.resource import get_driver
from webui.app_core import initializing_state, reset_to_initial
from spiderlx.ui.selenium import uixiaoyuan

INITIAL_STATE = {
    "step": 1,
    "browser_started": False,
    "web_name": "",
    "web_api": "",
    "web_open": False
}  # 初始状态


def show_state():
    st.write('selenium开启状态', st.session_state.browser_started)


def app_main():
    """
    selenium用户界面
    :return:
    """
    # ======================
    # web自动化首页
    # ======================
    initializing_state(INITIAL_STATE)
    with st.sidebar.container(border=True):
        st.image('https://www.runoob.com/wp-content/uploads/2025/01/selenium-automation.png')

        col1, col2, col3 = st.columns(3)
        with col1:
            if not st.session_state.browser_started:
                # 唤醒并配置浏览器
                if st.button('开启浏览器', type='primary', use_container_width=True):
                    if not st.session_state.browser_started:
                        get_driver()  # 使用浏览器驱动
                        st.session_state.app_home = False
                        st.session_state.browser_started = True  # 标记为已启动
                        # st.success("浏览器首次启动成功！")
                        st.rerun()
                    else:
                        st.warning("浏览器已启动，无需重复开启！")
            else:
                if st.button('关闭浏览器', use_container_width=True):
                    if st.session_state.browser_started:
                        get_driver().close_browser()
                        reset_to_initial(INITIAL_STATE)
                        get_driver.clear()
                        st.rerun()
                    else:
                        st.warning("浏览器未启动！")
        with col2:
            show_state()

        with col3:
            if st.button('返回上一步', use_container_width=True) and st.session_state.step > 1:
                st.session_state.step -= 1
                st.rerun()

    # -------- 浏览器打开后，步骤1：打开目标网站 --------
    if st.session_state.step == 1 and st.session_state.browser_started:
        st.subheader(f'selenium第{st.session_state.step}步')
        driver = get_driver()

        web_info = driver.website_info
        st.session_state.web_name = st.selectbox('请选择想要访问的网站', options=web_info.values())
        st.session_state.web_api = st.text_input("请输入要访问的web_api：", value="https://www.baidu.com")
        col1, col2 = st.columns(2)
        with col1:
            st.write('即将进入：', st.session_state.web_name)
            if st.button('打开已解析网站'):
                with st.spinner(f"正在打开{st.session_state.web_name}..."):
                    # 打开要访问的网站
                    name = driver.open_website(name=st.session_state.web_name)
                    if name == st.session_state.web_name:
                        st.success('网站已成功打开！')
                        st.session_state.web_open = True
                        # 进入第二步 —— 自动化解析网站
                        st.session_state.step = 2
                        st.rerun()  # 刷新进入步骤2
                    else:
                        st.warning('系统未记录登录信息！请手动登录，登录成功后，获取登录信息')
            if st.button('获取登录信息'):
                r = driver.get_cookies()
                st.write(r)
        with col2:
            st.write('即将进入：', st.session_state.web_api)
            if st.button('打开未解析网站'):
                with st.spinner(f"正在打开{st.session_state.web_api}..."):
                    # 打开要访问的网站
                    name = driver.open_website(url=st.session_state.web_api)
                    if name == st.session_state.web_api:
                        st.success('网站已成功打开！')
                        st.session_state.web_open = True
                        # 进入第二步 —— 自动化解析网站
                        st.session_state.step = 2
                        st.rerun()  # 刷新进入步骤2

    # -------- 浏览器打开后，步骤2：目标网站自动化解析 --------
    if st.session_state.step == 2 and st.session_state.browser_started:
        driver = get_driver()
        st.session_state.url = driver.get_current_url()
        with st.sidebar.container(border=True):
            st.subheader(f'selenium第{st.session_state.step}步，目标网站自动化解析')
            # aitools.main()

        if st.session_state.web_name == '小猿众包':
            uixiaoyuan.main()
        elif st.session_state.web_name == '':
            pass
        else:
            st.write('目标网站自动化待开发~~~')

    # -------- 步骤3：完成（可选） --------
    if st.session_state.step == 3 and st.session_state.browser_started:
        pass


if __name__ == '__main__':
    pass
