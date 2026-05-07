import sys
import os
import socket
import requests
import subprocess
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtWebEngineWidgets import QWebEngineView

# 常量
STREAMLIT_PORT = 8501
STREAMLIT_URL = f"http://localhost:{STREAMLIT_PORT}"


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect(('localhost', port))
            return True
        except socket.error:
            return False


def is_streamlit_running(url):
    try:
        response = requests.get(url, timeout=2)
        if response.status_code == 200 and "streamlit" in response.text.lower():
            return True
        return False
    except requests.RequestException:
        return False


class BrowserWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数据采集系统")
        self.setMinimumSize(400, 300)
        self.resize(950, 750)
        self.is_manual_stop = False  # 主动停止标志

        # 主容器
        main_container = QWidget()
        self.setCentralWidget(main_container)
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 浏览器控件
        self.web_view = QWebEngineView()
        self.web_view.loadStarted.connect(lambda: self.append_log("🔄 浏览器开始加载 Streamlit 页面..."))
        self.web_view.loadFinished.connect(self.on_page_loaded)
        main_layout.addWidget(self.web_view)

        # 日志面板
        self.log_dock = QDockWidget("运行日志", self)
        self.log_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable |
                                  QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFontFamily("Consolas")
        self.log_dock.setWidget(self.log_text)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.log_dock.hide()  # 初始隐藏

        # ========== 工具栏：两个按钮在同一行 ==========
        self.toolbar = self.addToolBar("控制")
        self.toolbar.setMovable(False)  # 可选：禁止移动

        # 按钮1：启动/停止 Streamlit
        self.toggle_btn = QPushButton()
        self.toggle_btn.clicked.connect(self.on_toggle_clicked)
        self.toolbar.addWidget(self.toggle_btn)

        # 按钮2：显示/隐藏日志（可勾选）
        self.log_btn = QPushButton("显示日志")
        self.log_btn.setCheckable(True)
        self.log_btn.toggled.connect(self.toggle_log_dock)
        self.toolbar.addWidget(self.log_btn)
        # ============================================

        # Streamlit 子进程
        self.streamlit_process = QProcess(self)
        self.streamlit_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.streamlit_process.readyReadStandardOutput.connect(self.on_streamlit_output)
        if sys.platform == "win32":
            try:
                def set_no_window(args):
                    args.flags |= subprocess.CREATE_NO_WINDOW

                self.streamlit_process.setCreateProcessArgumentsModifier(set_no_window)
            except AttributeError:
                pass
        self.streamlit_process.finished.connect(self.on_streamlit_finished)
        self.streamlit_process.errorOccurred.connect(self.on_streamlit_error)

        # 外部服务标记
        self.external_service = False

        # 启动或附加服务
        QTimer.singleShot(0, self.start_or_attach_streamlit)

    # ========== 日志相关 ==========
    def append_log(self, text):
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.log_text.append(f"[{timestamp}] {text}")

    def toggle_log_dock(self, checked):
        """根据按钮状态显示/隐藏日志面板"""
        if checked:
            self.log_dock.show()
            self.log_btn.setText("隐藏日志")
        else:
            self.log_dock.hide()
            self.log_btn.setText("显示日志")

    # ========== 按钮状态更新 ==========
    def update_button_state(self):
        """根据进程状态更新启停按钮的文本和启用状态"""
        if self.external_service:
            self.toggle_btn.setEnabled(False)
            self.toggle_btn.setText("外部服务运行中（不可控）")
        else:
            self.toggle_btn.setEnabled(True)
            if self.streamlit_process.state() == QProcess.ProcessState.NotRunning:
                self.toggle_btn.setText("启动 Streamlit")
            else:
                self.toggle_btn.setText("停止 Streamlit")

    def on_toggle_clicked(self):
        """启停按钮点击槽：根据当前状态启动或停止"""
        if self.streamlit_process.state() == QProcess.ProcessState.NotRunning:
            self.start_streamlit_manually()
        else:
            self.stop_streamlit_manually()

    # ========== 手动控制 ==========
    def start_streamlit_manually(self):
        """手动启动 Streamlit"""
        if self.streamlit_process.state() != QProcess.ProcessState.NotRunning:
            return
        if is_port_in_use(STREAMLIT_PORT) and is_streamlit_running(STREAMLIT_URL):
            QMessageBox.warning(self, "提示", "端口已被其他 Streamlit 服务占用，无法启动新进程。")
            return
        self.append_log("🚀 手动启动 Streamlit 服务...")
        self.start_streamlit_process()

    def stop_streamlit_manually(self):
        """手动停止 Streamlit"""
        if self.streamlit_process.state() == QProcess.ProcessState.NotRunning:
            return
        self.append_log("🛑 手动停止 Streamlit 服务...")
        self.terminate_streamlit_process()
        # 清空页面并显示提示
        self.web_view.setHtml("<html><body><h2>Streamlit 服务已停止</h2><p>请点击“启动 Streamlit”重新启动。</p></body></html>")

    # ========== 进程管理核心 ==========
    def start_streamlit_process(self):
        python_exe = sys.executable
        script_path = os.path.join(os.path.dirname(__file__), "streamlit_app.py")
        if not os.path.exists(script_path):
            self.append_log(f"❌ 找不到 Streamlit 脚本: {script_path}")
            QMessageBox.critical(self, "错误", f"Streamlit 脚本不存在：{script_path}")
            sys.exit(1)

        args = [
            python_exe, "-m", "streamlit", "run", script_path,
            "--server.port", str(STREAMLIT_PORT),
            "--server.headless", "true"
        ]
        self.streamlit_process.start(args[0], args[1:])
        if not self.streamlit_process.waitForStarted(3000):
            self.append_log("❌ Streamlit 启动失败！")
            QMessageBox.critical(self, "错误", "无法启动 Streamlit 服务。")
            sys.exit(1)
        else:
            self.append_log(f"📦 Streamlit 进程已启动 (PID: {self.streamlit_process.processId()})")
            self.update_button_state()

    def terminate_streamlit_process(self):
        """终止 Streamlit 进程（无弹窗）"""
        if self.streamlit_process.state() == QProcess.ProcessState.NotRunning:
            return
        self.streamlit_process.terminate()
        if not self.streamlit_process.waitForFinished(3000):
            self.streamlit_process.kill()
            self.streamlit_process.waitForFinished()
        self.append_log("✅ Streamlit 进程已停止")
        self.update_button_state()

    # ========== 信号处理 ==========
    def on_streamlit_output(self):
        data = self.streamlit_process.readAllStandardOutput()
        text = bytes(data).decode('utf-8', errors='replace')
        for line in text.splitlines():
            self.append_log(line.strip())
        if "You can now view your Streamlit app" in text:
            self.append_log("✅ Streamlit 服务已就绪，正在加载页面...")
            self.load_streamlit_page()

    def on_streamlit_error(self, error):
        self.append_log(f"❌ Streamlit 进程错误: {self.streamlit_process.errorString()}")
        QMessageBox.critical(self, "错误", f"Streamlit 进程异常：{self.streamlit_process.errorString()}")
        self.update_button_state()

    def on_streamlit_finished(self, exit_code, exit_status):
        self.append_log(f"🏁 Streamlit 进程已结束 (exit code: {exit_code})")
        if exit_code != 0:
            QMessageBox.warning(self, "警告", f"Streamlit 异常退出，代码 {exit_code}")
        self.update_button_state()

    # ========== 页面加载 ==========
    def load_streamlit_page(self):
        self.web_view.load(QUrl(STREAMLIT_URL))

    def on_page_loaded(self, success):
        if success:
            self.append_log("✅ 浏览器页面加载成功！")
        else:
            self.append_log("❌ 浏览器页面加载失败，5秒后重试...")
            QTimer.singleShot(5000, self.load_streamlit_page)

    # ========== 启动检测 ==========
    def start_or_attach_streamlit(self):
        if is_port_in_use(STREAMLIT_PORT):
            self.append_log(f"🔍 端口 {STREAMLIT_PORT} 已被占用，检查是否为 Streamlit 服务...")
            if is_streamlit_running(STREAMLIT_URL):
                self.append_log("✅ 检测到已有 Streamlit 服务在运行，将直接复用。")
                self.external_service = True
                self.update_button_state()
                self.load_streamlit_page()
            else:
                self.append_log("⚠️ 端口被占用但未检测到 Streamlit 服务，请手动关闭占用端口的程序后重试。")
                QMessageBox.critical(self, "错误", "端口被占用且不是 Streamlit 服务，无法继续。")
                sys.exit(1)
        else:
            self.external_service = False
            self.append_log("🚀 端口空闲，启动新的 Streamlit 服务...")
            self.start_streamlit_process()

    # ========== 关闭事件 ==========
    def closeEvent(self, event):
        """关闭窗口时直接终止由本程序启动的 Streamlit 进程（不弹窗）"""
        if not self.external_service and self.streamlit_process.state() != QProcess.ProcessState.NotRunning:
            self.append_log("正在关闭 Streamlit 进程...")
            self.terminate_streamlit_process()
        event.accept()


if __name__ == "__main__":
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL)
    app = QApplication(sys.argv)
    window = BrowserWindow()
    window.show()
    sys.exit(app.exec())
