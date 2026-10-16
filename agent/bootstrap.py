"""首启安装引导（安装包化 2026-10-16）：打包 exe 非安装位置双击时，

弹窗引导安装：选安装目录（默认 %LOCALAPPDATA%\\XiaoYuanAI）+ 桌面快捷方式
（默认勾选）→ 复制 exe 到 bin\\ → 旧数据自动迁移（exe 旁 data/ → 新数据根）→
启动安装后的副本退出。安装后数据统一落 %LOCALAPPDATA%\\XiaoYuanAI\\data，
再也不会散落到 exe 所在目录（桌面）——utils/data_path.root_path 的 frozen
分支负责运行时数据根。

设计（傻瓜操作为准）：一键默认即可完成，可选改目录；取消安装则直接退出。
"""

import os
import shutil
import subprocess
import sys

EXE_NAME = "小元AI Agent.exe"
DEFAULT_INSTALL_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "XiaoYuanAI")


def _exe_dir() -> str:
    return os.path.dirname(os.path.abspath(sys.executable))


def _copy_self(target_exe: str) -> None:
    """复制当前 exe 到目标（跨目录 shutil.copy2；正在运行的 exe 可复制）"""
    os.makedirs(os.path.dirname(target_exe), exist_ok=True)
    shutil.copy2(sys.executable, target_exe)


def _create_shortcut(target_exe: str, install_dir: str) -> bool:
    """桌面快捷方式（PowerShell WScript.Shell COM，零依赖）"""
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        "$lnk = [System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), '"
        + EXE_NAME.replace(".exe", "") + ".lnk'); "
        "$s = $ws.CreateShortcut($lnk); "
        "$s.TargetPath = '" + target_exe.replace("'", "''") + "'; "
        "$s.WorkingDirectory = '" + install_dir.replace("'", "''") + "'; "
        "$s.Save()"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       timeout=30, capture_output=True)
        return True
    except Exception:
        return False


def _migrate_old_data(install_dir: str) -> bool:
    """旧数据迁移：exe 旁 data/ 存在且新数据根 data/ 不存在 → 整体复制。
    （老用户把 exe 放桌面时的身份/配置/会话/日志全部无感搬过去）"""
    src = os.path.join(_exe_dir(), "data")
    if not os.path.isdir(src):
        return False
    dst = os.path.join(install_dir, "data")
    if os.path.isdir(dst):
        return False
    try:
        shutil.copytree(src, dst)
        return True
    except Exception:
        return False


def run_install_bootstrap() -> None:
    """安装引导主流程：弹窗 → 安装 → 启动新副本。用户取消 → sys.exit(0)"""
    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.withdraw()
    root.title("小元AI Agent 安装")

    # 确认安装（默认值一键可过）
    if not messagebox.askokcancel(
            "小元AI Agent 安装",
            "检测到你在直接运行安装包。\n\n"
            "点击「确定」安装到默认位置（%LOCALAPPDATA%\\XiaoYuanAI）\n"
            "并在桌面创建快捷方式；安装后请从快捷方式启动。\n\n"
            "安装位置可随后选择。"):
        sys.exit(0)

    install_dir = filedialog.askdirectory(
        title="选择安装位置",
        initialdir=DEFAULT_INSTALL_DIR,
        mustexist=False) or DEFAULT_INSTALL_DIR

    bin_dir = os.path.join(install_dir, "bin")
    target_exe = os.path.join(bin_dir, EXE_NAME)

    # 已在标准位置（重复安装）→ 直接启动
    if os.path.abspath(sys.executable) == os.path.abspath(target_exe):
        return

    try:
        _copy_self(target_exe)
    except Exception as e:
        messagebox.showerror("安装失败", f"复制程序失败：{e}")
        sys.exit(1)

    shortcut_ok = _create_shortcut(target_exe, bin_dir)
    migrated = _migrate_old_data(install_dir)

    msg = "安装完成！\n\n已安装到：%s" % bin_dir
    if shortcut_ok:
        msg += "\n已创建桌面快捷方式「%s」" % EXE_NAME.replace(".exe", "")
    else:
        msg += "\n（桌面快捷方式创建失败，可手动创建）"
    if migrated:
        msg += "\n旧数据已自动迁移"
    msg += "\n\n请从桌面快捷方式启动（本窗口将自动打开新程序）"
    messagebox.showinfo("安装完成", msg)

    # 启动安装后的副本，退出自身
    try:
        subprocess.Popen([target_exe], cwd=bin_dir,
                         creationflags=0x08000000 if os.name == "nt" else 0)
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    run_install_bootstrap()
