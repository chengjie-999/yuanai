import streamlit as st

from spider_lx.auto.web.selenium import selenium_cj
from spider_lx.parse_data import xiao_yuan


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

    # -------- 步骤1：打开目标网站 --------
    if st.session_state.step == 1 and st.session_state.browser_started:
        driver = st.session_state.web_driver
        info = selenium_cj.able_web()
        st.session_state.web_code = st.selectbox('请选择想要访问的网站', options=info.values())
        if st.button('打开网站'):
            selenium_cj.app_choose_web(driver, info, st.session_state.web_code)

    # -------- 步骤2：目标网站自动化解析 --------
    if st.session_state.step == 2:
        try:
            if st.session_state.web_name == '小猿众包':
                xiao_yuan.app_go(st.session_state.web_drive)
            else:
                st.write('目标网站自动化待开发~~~')
        except Exception as e:
            st.error(e.args)

    # -------- 步骤3：完成（可选） --------
    if st.session_state.step == 3:
        pass


if __name__ == '__main__':
    info = selenium_cj.able_web()
    print(info.values())
