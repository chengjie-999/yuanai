import streamlit as st

from utils.app_core import initializing_state, reset_to_initial
from spiderlx.auto.web.selenium import main as selenium_cj
from spiderlx.ui import uixiaoyuan

INITIAL_STATE = {
    "step": 1,
    "web_driver": "",
    "browser_started": False,
    "url": "",
    "web_name": "",
    "web_open": False
}  # 初始状态


# @st.cache_resource
def get_driver():
    """
    获取浏览器驱动，并加入缓存
    :return:浏览器驱动
    """
    return selenium_cj.chrome()


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
                        st.session_state.web_driver = get_driver()  # 使用浏览器驱动
                        st.session_state.app_home = False
                        st.session_state.browser_started = True  # 标记为已启动
                        # st.success("浏览器首次启动成功！")
                        st.rerun()
                    else:
                        st.warning("浏览器已启动，无需重复开启！")
            else:
                if st.button('关闭浏览器', use_container_width=True):
                    if st.session_state.browser_started:
                        st.session_state.web_driver.quit()
                        reset_to_initial(INITIAL_STATE)
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
        driver = st.session_state.web_driver
        web_info = selenium_cj.able_web()
        st.session_state.web_name = st.selectbox('请选择想要访问的网站', options=web_info.values())
        st.write('即将进入：', st.session_state.web_name)
        if st.button('打开网站'):
            with st.spinner(f"正在打开{st.session_state.web_name}..."):
                # 打开要访问的网站
                name = selenium_cj.open_web(driver, web_info, st.session_state.web_name)
                if name == st.session_state.web_name:
                    st.success('网站已成功打开！')
                    st.session_state.web_open = True
                    # 进入第二步 —— 自动化解析网站
                    st.session_state.step = 2
                    st.rerun()  # 刷新进入步骤2

    # -------- 浏览器打开后，步骤2：目标网站自动化解析 --------
    if st.session_state.step == 2 and st.session_state.browser_started:
        with st.sidebar.container(border=True):
            st.subheader(f'selenium第{st.session_state.step}步，目标网站自动化解析')
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
    info = selenium_cj.able_web()
    print(info.values())
