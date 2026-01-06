import streamlit as st

from spider_lx.auto.web.selenium import selenium_cj
from spider_lx.parse_data import xiao_yuan
from spider_lx.ui import xiao_yuan_ui


def app_main():
    """
    selenium用户界面
    :return:
    """
    col1, col2 = st.columns(2)
    with col1:
        # 唤醒并配置浏览器
        if st.button('开启浏览器'):
            if not st.session_state.browser_started:
                st.session_state.web_driver = selenium_cj.chrome()  # 传入实例
                st.session_state.browser_started = True  # 标记为已启动
                st.success("浏览器首次启动成功！")
            else:
                st.warning("浏览器已启动，无需重复开启！")
    with col2:
        if st.button('关闭浏览器'):
            if st.session_state.browser_started:
                st.session_state.web_driver.quit()
                st.session_state.web_driver = None
                st.session_state.browser_started = False
            else:
                st.warning("浏览器未启动！")

    # -------- 浏览器打开后，步骤1：打开目标网站 --------
    if st.session_state.step == 1 and st.session_state.browser_started:
        driver = st.session_state.web_driver
        web_info = selenium_cj.able_web()
        st.session_state.web_name = st.selectbox('请选择想要访问的网站', options=web_info.values())
        st.write('即将进入：', st.session_state.web_name)
        if st.button('打开网站'):
            name = selenium_cj.open_web(driver, web_info, st.session_state.web_name)
            if name == st.session_state.web_name and not st.session_state.web_open:
                st.success('网站已成功打开！')
                st.session_state.web_open = True
                st.session_state.step = 2
            else:
                st.warning('已经有网页打开')

    # -------- 浏览器打开后，步骤2：目标网站自动化解析 --------
    if st.session_state.step == 2 and st.session_state.browser_started:
        try:
            if st.session_state.web_name == '小猿众包':
                xiao_yuan_ui.main()
            else:
                st.write('目标网站自动化待开发~~~')
        except Exception as e:
            st.error(e.args)

    # -------- 步骤3：完成（可选） --------
    if st.session_state.step == 3 and st.session_state.browser_started:
        pass


if __name__ == '__main__':
    info = selenium_cj.able_web()
    print(info.values())
