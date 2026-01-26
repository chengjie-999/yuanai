# 导入所需库
from selenium import webdriver
from selenium.webdriver.common.by import By
from PIL import Image
import streamlit as st
import io
import time


def get_element_screenshot_png():
    """获取 WebElement 截图的二进制数据（bytes 类型）"""
    # 初始化 Chrome 浏览器驱动（无头模式，不弹出浏览器窗口，适合 Streamlit 运行）
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless=new")  # 新版 Chrome 无头模式
    chrome_options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        # 打开测试页面（百度首页）
        driver.get("https://www.baidu.com")
        time.sleep(1)  # 等待页面完全加载

        # 定位目标元素（百度搜索框）
        target_element = driver.find_element(By.ID, "kw")

        # 获取元素截图的二进制数据（bytes）—— 核心返回值
        png_binary_data = target_element.screenshot_as_png
        return png_binary_data

    finally:
        # 确保浏览器关闭
        driver.quit()


def display_screenshot_in_streamlit(png_bytes):
    """将二进制图片数据在 Streamlit 中显示"""
    # 方法1：将 bytes 数据转换成 PIL.Image 对象（推荐，兼容性更好）
    # 1. 用 io.BytesIO 封装二进制数据，形成字节流
    image_stream = io.BytesIO(png_bytes)
    # 2. 用 PIL.Image 打开字节流，转换成图片对象
    screenshot_image = Image.open(image_stream)

    # 3. 用 streamlit.st.image() 显示图片
    st.subheader("WebElement 元素截图展示")
    st.image(
        screenshot_image,
        caption="百度搜索框元素截图（来自 Selenium screenshot_as_png）",
        use_column_width=True  # 自适应列宽显示
    )

    # 方法2：直接将 bytes 数据传入 st.image()（简化版，无需 PIL）
    st.subheader("简化版：直接传入二进制数据显示")
    st.image(
        png_bytes,
        caption="无需 PIL 转换，直接显示 bytes 类型图片数据",
        use_column_width=True
    )


# Streamlit 页面主逻辑
if __name__ == "__main__":
    st.title("Selenium 元素截图 → Streamlit 显示演示")

    # 按钮触发截图和显示
    if st.button("获取并显示元素截图"):
        with st.spinner("正在获取元素截图..."):
            pass
            # 1. 获取截图二进制数据
            element_png_data = get_element_screenshot_png()

            # 2. 验证数据并显示
            if element_png_data:
                st.success("截图二进制数据获取成功！")
                display_screenshot_in_streamlit(element_png_data)

                # 可选：查看二进制数据的基本信息（验证数据有效性）
                with st.expander("查看截图二进制数据详情"):
                    st.write(f"二进制数据类型：{type(element_png_data)}")
                    st.write(f"二进制数据大小：{len(element_png_data)} 字节")
                    st.write(f"二进制数据前 50 个字节：{element_png_data[:50]}")
            else:
                st.error("截图获取失败，请检查网络或元素定位！")
