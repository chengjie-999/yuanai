from spiderlx.auto.web.selenium.main import MyWebBrowser, BrowserInitializer
import streamlit as st


@st.cache_resource(show_spinner="正在启动浏览器...")
def get_driver():
    """
    获取浏览器驱动，并加入缓存
    :return:浏览器驱动
    """
    return MyWebBrowser(BrowserInitializer().create_driver())
