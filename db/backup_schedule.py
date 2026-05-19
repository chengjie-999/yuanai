"""Windows 定时备份任务管理 — 通过 schtasks 实现每周自动备份

用法:
    python -m db.backup_schedule install   # 安装每周日凌晨 3 点备份
    python -m db.backup_schedule install --day MON --time 02:00   # 自定义时间
    python -m db.backup_schedule uninstall # 卸载
    python -m db.backup_schedule status    # 查看状态
"""
import sys
import os
import subprocess
import argparse

TASK_NAME = "yuanai-db-backup"


def _schtasks(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def install(day: str = "SUN", time: str = "03:00"):
    if sys.platform != "win32":
        print("此工具仅支持 Windows Task Scheduler")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    backup_py = os.path.join(script_dir, "backup.py")
    python_exe = sys.executable
    # 用 python -m db.backup 以便工作目录正确
    cmd = (
        f'schtasks /create /sc weekly /d {day} /tn "{TASK_NAME}" '
        f'/tr "\\"{python_exe}\\" -m db.backup" '
        f'/st {time} /f'
    )
    print(f"创建任务: 每周 {day} {time}")
    result = _schtasks(cmd)
    if result.returncode == 0:
        print(f"✓ 任务 '{TASK_NAME}' 已创建")
        print(f"  tr: {python_exe} -m db.backup")
        print(f"  sc: weekly / d:{day} / st:{time}")
    else:
        print(f"✗ 创建失败: {result.stderr}")


def uninstall():
    if sys.platform != "win32":
        return
    result = _schtasks(f'schtasks /delete /tn "{TASK_NAME}" /f')
    if result.returncode == 0:
        print(f"✓ 任务 '{TASK_NAME}' 已删除")
    else:
        print(f"任务不存在或删除失败: {result.stderr}")


def status():
    if sys.platform != "win32":
        print("此工具仅支持 Windows")
        return
    result = _schtasks(f'schtasks /query /tn "{TASK_NAME}" /fo LIST /v')
    if result.returncode != 0:
        print(f"任务 '{TASK_NAME}' 未找到")
        return
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith(("TaskName:", "Schedule:", "Start Time:", "Status:")):
            print(line)


def main():
    parser = argparse.ArgumentParser(description="数据库每周备份定时任务管理")
    sub = parser.add_subparsers(dest="action")

    p_install = sub.add_parser("install", help="安装每周备份任务")
    p_install.add_argument("--day", default="SUN", help="星期几 (MON/TUE/WED/THU/FRI/SAT/SUN)")
    p_install.add_argument("--time", default="03:00", help="执行时间 (HH:MM)")

    sub.add_parser("uninstall", help="卸载定时任务")
    sub.add_parser("status", help="查看任务状态")

    args = parser.parse_args()
    if args.action == "install":
        install(args.day, args.time)
    elif args.action == "uninstall":
        uninstall()
    elif args.action == "status":
        status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
