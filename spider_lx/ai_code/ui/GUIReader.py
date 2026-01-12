import tkinter as tk
import threading
import time


class GUIReader:
    def __init__(self, root):
        self.root = root
        self.root.title("子线程读取 GUI 内容")
        self.root.geometry("350x200")

        # 1. GUI 组件：输入框（让用户输入参数）
        self.param_label = tk.Label(root, text="请输入任务参数（数字）：")
        self.param_label.pack(pady=10)
        self.param_entry = tk.Entry(root, width=20)
        self.param_entry.insert(0, "5")  # 默认值
        self.param_entry.pack(pady=5)

        # 2. 控制按钮
        self.start_btn = tk.Button(root, text="启动子线程读取", command=self.start_thread)
        self.start_btn.pack(pady=10)

        # 3. 状态显示
        self.status_label = tk.Label(root, text="未启动", font=("Arial", 10))
        self.status_label.pack(pady=5)

    def start_thread(self):
        """启动子线程（读取 GUI 内容）"""
        self.start_btn.config(state=tk.DISABLED)  # 防止重复启动
        self.status_label.config(text="子线程运行中...")

        # 创建子线程（守护线程）
        self.read_thread = threading.Thread(target=self.read_gui_content, daemon=True)
        self.read_thread.start()

    def read_gui_content(self):
        """子线程：读取 GUI 输入框的内容"""
        # 直接读取 GUI 组件的内容（无并发冲突，因为启动后用户不修改）
        gui_param = self.param_entry.get()

        # 数据容错处理（确保读取的是数字）
        try:
            param = int(gui_param)
        except ValueError:
            param = 5  # 默认值
            # 子线程不能直接修改 GUI，通过 root.after() 通知主线程更新状态
            self.root.after(0, self.update_status, f"输入无效，使用默认参数：{param}")
        else:
            self.root.after(0, self.update_status, f"读取到参数：{param}，开始执行任务...")

        # 模拟业务逻辑（使用读取到的 GUI 参数）
        for i in range(param):
            print(f"子线程任务执行中 | 第 {i + 1} 次 | 参数：{param}")
            time.sleep(1)

        # 任务结束，更新 GUI 状态
        self.root.after(0, self.update_status, "子线程结束")
        self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))

    def update_status(self, msg):
        """主线程：更新 GUI 状态（子线程通过 after() 调用）"""
        self.status_label.config(text=msg)


if __name__ == "__main__":
    root = tk.Tk()
    app = GUIReader(root)
    root.mainloop()