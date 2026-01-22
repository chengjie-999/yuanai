import streamlit as st

from spider_lx.auto.web.selenium import main as selenium_cj
from spider_lx.ui import xiao_yuan_ui

INITIAL_STATE = {
    "step": 1,
    "web_driver": "",
    "browser_started": False,
    "url": "",
    "web_name": "",
    "web_open": False
}  # 初始状态


def initializing_state():
    """
    初始化selenium_ui的会话状态（跨步骤保存数据）
    :return:
    """
    for key, default_val in INITIAL_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = default_val


def reset_to_initial():
    """回归初始化状态：用保留的初始模板重置所有状态"""
    for key, default_val in INITIAL_STATE.items():
        st.session_state[key] = default_val  # 强制覆盖为初始值


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
    initializing_state()
    # 侧边栏
    st.sidebar.write('【selenium初始状态】', INITIAL_STATE)
    st.sidebar.write('【selenium当前状态】')
    for k in INITIAL_STATE:
        st.sidebar.write(k, st.session_state[k])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if not st.session_state.browser_started:
            # 唤醒并配置浏览器
            if st.button('开启浏览器', use_container_width=True):
                if not st.session_state.browser_started:
                    st.session_state.web_driver = get_driver()  # 使用浏览器驱动
                    st.session_state.browser_started = True  # 标记为已启动
                    st.success("浏览器首次启动成功！")
                    st.rerun()
                else:
                    st.warning("浏览器已启动，无需重复开启！")
        else:
            if st.button('关闭浏览器', use_container_width=True):
                if st.session_state.browser_started:
                    st.session_state.web_driver.quit()
                    reset_to_initial()
                    st.rerun()
                else:
                    st.warning("浏览器未启动！")
    with col2:
        show_state()

    with col3:
        if st.button('返回上一步', use_container_width=True) and st.session_state.step > 1:
            st.session_state.step -= 1
            st.rerun()
    with col4:
        if st.button('重载', use_container_width=True):
            st.rerun()

    # -------- 浏览器打开后，步骤1：打开目标网站 --------
    if st.session_state.step == 1 and st.session_state.browser_started:
        st.subheader(f'selenium第{st.session_state.step}步')
        driver = st.session_state.web_driver
        web_info = selenium_cj.able_web()
        st.session_state.web_name = st.selectbox('请选择想要访问的网站', options=web_info.values())
        st.write('即将进入：', st.session_state.web_name)
        if st.button('打开网站'):
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
        st.subheader(f'selenium第{st.session_state.step}步，目标网站自动化解析')
        if st.session_state.web_name == '小猿众包':
            xiao_yuan_ui.main()
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
