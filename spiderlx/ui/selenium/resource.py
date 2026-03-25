import streamlit as st

from spiderlx.auto.web.selenium.main import MyWebBrowser, BrowserInitializer


@st.cache_resource(show_spinner="正在加载浏览器，请稍候...")
def get_driver():
    """
    获取浏览器驱动，并加入缓存
    :return:浏览器驱动
    """
    return MyWebBrowser(BrowserInitializer().create_driver())
