import streamlit as st
from spider_lx.parse_data import xiao_yuan


def main():
    xiao_yuan.go(st.session_state.web_drive)
