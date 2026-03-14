from spiderlx.auto.web.playwrightdo.main import init_playwright_browser
from multiprocessing import Process, Queue
import time
import traceback
import streamlit as st
import re


# --------------------------
# 1. 工具函数：验证URL合法性
# --------------------------
def is_valid_url(url):
    """检查URL是否有效（非空 + 以http/https开头）"""
    if not url or url.strip() == "":
        return False
    pattern = re.compile(r'^https?://.+$', re.IGNORECASE)
    return bool(pattern.match(url.strip()))


# --------------------------
# 2. 初始化会话态（仅初始化一次）
# --------------------------
def init_pw_state():
    if "pw_cmd_queue" not in st.session_state:
        st.session_state.pw_cmd_queue = Queue()
    if "pw_res_queue" not in st.session_state:
        st.session_state.pw_res_queue = Queue()
    if "pw_worker_process" not in st.session_state:
        st.session_state.pw_worker_process = None


# --------------------------
# 3. Playwright子进程（核心修复：从队列传URL）
# --------------------------
def playwright_worker(cmd_queue, res_queue):
    browser = None
    pw_context = None
    try:
        from playwright.sync_api import sync_playwright
        # 手动管理Playwright上下文，避免Event loop closed
        pw = sync_playwright().start()
        pw_context = pw

        # 初始化浏览器（调用你的函数）
        browser, context, page = init_playwright_browser(pw, headless=False)
        page = page or browser.new_page()
        page.set_default_timeout(10000)

        # 循环监听指令
        while True:
            if not cmd_queue.empty():
                cmd = cmd_queue.get()

                # 爬取指令：先读URL，再验证，再执行
                if cmd == "scrape":
                    # 从队列读取URL（跨进程传参的核心）
                    url = cmd_queue.get() if not cmd_queue.empty() else ""

                    # 第一步：验证URL合法性
                    if not is_valid_url(url):
                        err_msg = f"无效URL：{url}\n请输入以 http/https 开头的合法地址！"
                        res_queue.put(("error", err_msg))
                        continue

                    # 第二步：执行爬取（仅URL合法时）
                    try:
                        page.goto(url.strip(), wait_until="load")
                        title = page.title()
                        res_queue.put(("success", f"✅ 爬取成功\nURL：{url.strip()}\n标题：{title}"))
                    except Exception as e:
                        err_msg = f"❌ 爬取失败：{str(e)}"
                        res_queue.put(("error", err_msg))

                # 退出指令
                elif cmd == "exit":
                    break

                time.sleep(0.1)

    except Exception as e:
        res_queue.put(("error", f"❌ 浏览器初始化失败：{str(e)}"))
    finally:
        # 确保资源正常关闭
        if browser:
            try:
                browser.close()
            except:
                pass
        if pw_context:
            pw_context.stop()


# --------------------------
# 4. 主入口（被render_toggle_button调用）
# --------------------------
def main():
    init_pw_state()
    st.subheader("Playwright 爬虫模块")

    # 按钮1：启动进程（唯一key）
    if st.button("📌 启动Playwright进程", key="pw_start_btn"):
        if not st.session_state.pw_worker_process:
            st.session_state.pw_worker_process = Process(
                target=playwright_worker,
                args=(st.session_state.pw_cmd_queue, st.session_state.pw_res_queue)
            )
            st.session_state.pw_worker_process.start()
            st.success("✅ Playwright进程已启动！")
        else:
            st.warning("⚠️ 进程已启动，无需重复操作！")

    # 按钮2：停止进程（唯一key）
    if st.button("🛑 停止Playwright进程", key="pw_stop_btn"):
        if st.session_state.pw_worker_process:
            st.session_state.pw_cmd_queue.put("exit")
            if st.session_state.pw_worker_process.is_alive():
                st.session_state.pw_worker_process.join(timeout=5)
            st.session_state.pw_worker_process = None
            st.info("✅ Playwright进程已停止！")
        else:
            st.warning("⚠️ 进程未启动，无需停止！")

    # 按钮3：执行爬取（唯一key）
    if st.button("🚀 执行爬取", key="pw_scrape_btn"):
        # 先检查进程是否启动
        if not st.session_state.pw_worker_process:
            st.error("❌ 请先启动Playwright进程！")
        else:
            # 从主页面session_state获取URL
            target_url = st.session_state.get("url", "https://www.baidu.com")

            # 发送爬取指令 + URL（跨进程传参）
            st.session_state.pw_cmd_queue.put("scrape")
            st.session_state.pw_cmd_queue.put(target_url)

            # 等待并展示结果
            start_time = time.time()
            result = None
            while time.time() - start_time < 10:  # 10秒超时
                if not st.session_state.pw_res_queue.empty():
                    result = st.session_state.pw_res_queue.get()
                    break
                time.sleep(0.1)

            # 展示结果
            if result:
                if result[0] == "success":
                    st.success(result[1])
                else:
                    st.error(result[1])
            else:
                st.warning("⚠️ 爬取超时（10秒），请检查URL或网络！")

    # 显示当前URL（和主页面同步）
    st.info(f"当前待爬取URL：{st.session_state.get('url', '未设置')}")