import subprocess
import os
from langchain_core.tools import tool


@tool("start_chrome", return_direct=True, description="启动 Chrome 浏览器并开启 9222 调试端口")
def start_chrome():
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    # 核心修复：用绝对路径 + 确保目录存在
    profile_dir = os.path.abspath("chrome_profile")  # 转为绝对路径
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)  # 自动创建目录，避免权限问题

    cmd = [
        chrome_path,
        "--remote-debugging-port=9222",
        "--start-maximized",  # 最大化窗口（真人习惯）
        f"--user-data-dir={profile_dir}",  # 用绝对路径
        "https://www.baidu.com"
    ]
    # 去掉 stdout/stderr 隐藏，方便调试（可选）
    subprocess.Popen(cmd)
    print(f"Chrome 已启动 9222 调试模式，配置目录：{profile_dir}")


if __name__ == "__main__":
    start_chrome()
