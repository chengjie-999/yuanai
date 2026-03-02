import os
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox


def merge_excel_sheets():
    """
    Excel工作表合并工具：点击按钮选文件 + 自定义输出文件名
    """
    # 初始化主窗口（全程可见，按钮触发选文件）
    root = tk.Tk()
    root.title("Excel合并工具")
    root.geometry("450x220")
    root.resizable(True, True)

    # 定义全局变量存储选中的文件路径
    selected_file_path = tk.StringVar(value="未选择文件")
    output_name_var = tk.StringVar(value="合并结果")

    # ========== 1. 点击按钮选择文件的函数 ==========
    def select_excel_file():
        file_path = filedialog.askopenfilename(
            title="请选择要合并工作表的Excel文件",
            filetypes=[("Excel文件", "*.xlsx"), ("Excel 97-2003文件", "*.xls"), ("所有文件", "*.*")],
            parent=root  # 绑定到主窗口，避免遮挡
        )
        if file_path:
            # 更新选中文件显示，并自动填充默认文件名
            selected_file_path.set(file_path)
            original_name = os.path.splitext(os.path.basename(file_path))[0]
            output_name_var.set(f"{original_name}_合并结果")

    # ========== 2. 执行合并的核心函数 ==========
    def run_merge():
        file_path = selected_file_path.get()
        output_name = output_name_var.get().strip()

        # 输入校验
        if file_path == "未选择文件":
            messagebox.showwarning("警告", "请先点击「选择文件」按钮选择要合并的Excel文件！")
            return
        if not output_name:
            messagebox.showwarning("警告", "合并后的文件名不能为空！")
            return

        try:
            # 读取Excel工作表
            excel_file = pd.ExcelFile(file_path)
            sheets = excel_file.sheet_names
            if not sheets:
                messagebox.showinfo("提示", "该Excel文件中没有可识别的工作表！")
                return

            # 合并所有非空工作表
            df_list = []
            for sheet in sheets:
                df = pd.read_excel(file_path, sheet_name=sheet)
                if not df.empty:
                    df["来源工作表"] = sheet  # 标记数据来源
                    df_list.append(df)

            if not df_list:
                messagebox.showinfo("提示", "所有工作表均无有效数据，无需合并！")
                return

            final_df = pd.concat(df_list, ignore_index=True)

            # 处理输出文件路径（自动补后缀、处理重名）
            output_dir = os.path.dirname(file_path)
            if not output_name.endswith(".xlsx"):
                output_name += ".xlsx"
            out_path = os.path.join(output_dir, output_name)

            # 避免覆盖已有文件
            num = 1
            while os.path.exists(out_path):
                name_no_ext = os.path.splitext(output_name)[0]
                out_path = os.path.join(output_dir, f"{name_no_ext}_{num}.xlsx")
                num += 1

            # 保存文件
            final_df.to_excel(out_path, index=False)
            messagebox.showinfo("合并成功",
                                f"共合并 {len(sheets)} 个工作表（{len(df_list)} 个有数据）\n文件已保存至：\n{out_path}")

        except Exception as e:
            messagebox.showerror("合并失败", f"出错原因：{str(e)}\n请检查文件是否损坏或格式正确")

    # ========== 界面布局（按钮触发选文件） ==========
    # 1. 选择文件区域
    tk.Label(root, text="步骤1：选择要合并工作表的Excel文件", font=("微软雅黑", 10, "bold")).pack(pady=8)
    frame_file = tk.Frame(root)
    frame_file.pack(fill=tk.X, padx=20)
    tk.Label(frame_file, textvariable=selected_file_path, fg="gray", font=("微软雅黑", 9)).pack(side=tk.LEFT, fill=tk.X, expand=True)
    tk.Button(frame_file, text="选择文件", command=select_excel_file,
              width=10, font=("微软雅黑", 9)).pack(side=tk.RIGHT)

    # 2. 自定义文件名区域
    tk.Label(root, text="步骤2：输入合并后的文件名", font=("微软雅黑", 10, "bold")).pack(pady=8)
    frame_name = tk.Frame(root)
    frame_name.pack(fill=tk.X, padx=20)
    tk.Entry(frame_name, textvariable=output_name_var, font=("微软雅黑", 9), width=30).pack(side=tk.LEFT, padx=5)
    tk.Label(frame_name, text=".xlsx", font=("微软雅黑", 9)).pack(side=tk.LEFT)

    # 3. 执行合并按钮
    tk.Button(root, text="开始合并", command=run_merge,
              width=15, height=1, font=("微软雅黑", 10, "bold"),
              bg="#4CAF50", fg="white").pack(pady=15)

    # 启动主循环
    root.mainloop()


if __name__ == "__main__":
    # 解决Windows系统tkinter界面模糊/中文问题
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
    merge_excel_sheets()