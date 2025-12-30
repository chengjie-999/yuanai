import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# 1. 初始化会话状态：记录 driver 实例和启动状态
if "driver" not in st.session_state:
    st.session_state.driver = None  # 存储 webdriver 实例
if "browser_started" not in st.session_state:
    st.session_state.browser_started = False  # 标记浏览器是否已启动

# 2. 启动浏览器按钮（仅首次点击/未启动时执行）
if st.button("启动浏览器"):
    if not st.session_state.browser_started:
        # 仅当浏览器未启动时，才初始化
        st.session_state.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install())
        )
        st.session_state.driver.get("https://www.baidu.com")
        st.session_state.browser_started = True  # 标记为已启动
        st.success("浏览器首次启动成功！")
    else:
        st.warning("浏览器已启动，无需重复开启！")

# 3. 手动触发 rerun（测试验证）
st.button("触发 rerun", on_click=st.rerun)

# 4. 验证：rerun 后仍能获取原有浏览器的页面信息
if st.session_state.driver is not None:
    page_title = st.session_state.driver.title
    st.info(f"当前浏览器页面标题（rerun 后仍有效）：{page_title}")

# 5. 关闭浏览器（重置状态）
if st.button("关闭浏览器"):
    if st.session_state.driver is not None:
        st.session_state.driver.quit()
        st.session_state.driver = None
        st.session_state.browser_started = False
        st.success("浏览器已关闭！")