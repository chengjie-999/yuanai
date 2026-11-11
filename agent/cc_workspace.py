"""CC 委派工作仓库解析（2026-11-08 建；2026-11 增强：持久化可配置）

工作目录选择链（优先级高 → 低）：
  1. 环境变量 CC_PROJECT_DIR（进程级覆盖，老手 / CI 用）
  2. 数据根下 cc_config.json 的 project_dir（set_project_dir 落盘——用户
     无需改系统环境变量、无需重启即可切换；CLI / 托盘 / 后台均可写）
  3. 源码模式 → 源码仓库根；冻结 exe → 数据根下内建 workspace
     （惰性初始化 guard 三件套，傻瓜设计：用户零配置零环境变量）

安全不变：guard 落地 + settings 注册是 guard_ready fail-closed 门禁的
前提，本模块只补「存在性」与「目录选择」，不削弱任何校验——配置若指向
没有 guard 的目录，guard_ready 仍 fail-closed 拒绝 spawn 子进程。

CLI 自检 / 切换：
  python -m agent.cc_workspace --show
  python -m agent.cc_workspace --set "D:\\code\\myproj"
  python -m agent.cc_workspace --clear
"""

import json
import os
import shutil
import sys
import tempfile

WORKSPACE_NAME = "workspace"
CONFIG_NAME = "cc_config.json"
CONFIG_KEY = "project_dir"

# .claude/settings.json 模板：command 用 $CLAUDE_PROJECT_DIR（CC 执行钩子时
# 自动替换为该仓库绝对路径）——与源码仓库模板同文，路径无关
_SETTINGS_TEMPLATE = """{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python \\"$CLAUDE_PROJECT_DIR/scripts/hooks/claude_guard.py\\"",
            "timeout": 15
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash|Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python \\"$CLAUDE_PROJECT_DIR/scripts/hooks/claude_guard.py\\"",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
"""


# ===================== 配置文件读写 =====================

def config_file() -> str:
    """配置文件绝对路径（数据根下，随 exe 升级不丢）：
    冻结模式 %LOCALAPPDATA%\\XiaoYuanAI\\cc_config.json；
    源码模式同为数据根（不污染仓库、不进 git status）"""
    from utils.data_path import frozen_data_root
    return os.path.join(frozen_data_root(), CONFIG_NAME)


def _norm(path: str) -> str:
    return os.path.abspath(os.path.expanduser(str(path).strip().strip('"')))


def read_config() -> dict:
    """读配置（任何异常都当空配置——配置坏了不能拖垮 agent 启动）"""
    try:
        with open(config_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_config(data: dict) -> str:
    """原子落盘（同目录临时文件 + os.replace），返回配置文件路径"""
    path = config_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".cc_config_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return path


def get_configured_dir() -> str:
    """配置目录（仅当存在且是目录时返回，否则 ""——配置失效自动回落）"""
    raw = read_config().get(CONFIG_KEY) or ""
    if not raw:
        return ""
    try:
        p = _norm(raw)
    except Exception:
        return ""
    return p if os.path.isdir(p) else ""


def validate_target(path: str) -> str:
    """校验切换目标，返回规范化绝对路径；不合法抛 ValueError

    只拦「明显不该当工作仓库」的目标（盘符根 / 用户主目录 / 系统目录），
    其余交给 guard_ready 的 fail-closed 门禁判定——本模块不重复安全策略。
    """
    if not str(path or "").strip():
        raise ValueError("路径为空")
    p = _norm(path)
    if not os.path.exists(p):
        raise ValueError(f"目录不存在: {p}")
    if not os.path.isdir(p):
        raise ValueError(f"不是目录: {p}")
    drive, tail = os.path.splitdrive(p)
    if not tail.strip("\\/"):
        raise ValueError(f"不能把盘符根目录当作工作仓库: {p}")
    if os.path.normcase(p) == os.path.normcase(_norm(os.path.expanduser("~"))):
        raise ValueError(f"不能把用户主目录当作工作仓库: {p}")
    return p


def set_project_dir(path: str) -> str:
    """持久化切换 CC 工作目录（下一轮 spawn 即生效，无需重启 agent）"""
    p = validate_target(path)
    data = read_config()
    data[CONFIG_KEY] = p
    _write_config(data)
    return p


def clear_project_dir() -> bool:
    """清除持久化配置（回落到 源码根 / 内建 workspace）；返回是否原本有配置"""
    data = read_config()
    if CONFIG_KEY not in data:
        return False
    data.pop(CONFIG_KEY, None)
    _write_config(data)
    return True


# ===================== 目录解析 =====================

def resolve_project_dir() -> str:
    """返回 CC 委派的工作仓库根：CC_PROJECT_DIR → cc_config.json → 默认根"""
    env_dir = os.getenv("CC_PROJECT_DIR", "")
    if env_dir and os.path.isdir(env_dir):
        return os.path.abspath(env_dir)
    cfg_dir = get_configured_dir()
    if cfg_dir:
        return cfg_dir
    if not getattr(sys, "frozen", False):
        # 源码模式：仓库根自带 scripts/hooks 与 .claude/settings.json
        from utils.data_path import root_path
        return root_path()
    from utils.data_path import frozen_data_root
    ws = os.path.join(frozen_data_root(), WORKSPACE_NAME)
    _init_workspace(ws)
    return ws


def ensure_cc_workspace() -> str:
    """兼容旧调用点：等价 resolve_project_dir()"""
    return resolve_project_dir()


def resolve_source() -> str:
    """当前目录来源标记（env / config / source-root / frozen-workspace），供 UI 展示"""
    env_dir = os.getenv("CC_PROJECT_DIR", "")
    if env_dir and os.path.isdir(env_dir):
        return "env"
    if get_configured_dir():
        return "config"
    return "frozen-workspace" if getattr(sys, "frozen", False) else "source-root"


def describe() -> dict:
    """自检信息：目录、来源、配置文件、安全钩子是否就绪"""
    root = resolve_project_dir()
    try:
        from agent.bridge_policy import guard_ready  # 延迟导入避免环
        ok, reason = guard_ready(root)
    except Exception as e:  # pragma: no cover - 仅在异常环境触发
        ok, reason = False, f"guard 检查异常: {e}"
    return {
        "project_dir": root,
        "source": resolve_source(),
        "config_file": config_file(),
        "guard_ready": ok,
        "guard_reason": reason,
        "env_override": bool(os.getenv("CC_PROJECT_DIR", "")),
    }


def _init_workspace(ws: str) -> None:
    """惰性初始化：钩子脚本（打包内置模板）+ settings.json 注册；幂等"""
    guard_dst = os.path.join(ws, "scripts", "hooks", "claude_guard.py")
    if not os.path.isfile(guard_dst):
        guard_src = os.path.join(getattr(sys, "_MEIPASS", ""),
                                 "scripts", "hooks", "claude_guard.py")
        if os.path.isfile(guard_src):
            os.makedirs(os.path.dirname(guard_dst), exist_ok=True)
            shutil.copy2(guard_src, guard_dst)
    settings_dst = os.path.join(ws, ".claude", "settings.json")
    if not os.path.isfile(settings_dst):
        os.makedirs(os.path.dirname(settings_dst), exist_ok=True)
        with open(settings_dst, "w", encoding="utf-8") as f:
            f.write(_SETTINGS_TEMPLATE)


def pick_directory(title: str = "选择文件夹") -> str:
    """原生 Windows 目录选择器（FolderBrowserDialog，经 PowerShell 独立进程弹出）。
    结果经临时文件以 UTF-8 传回——绕开 pystray 回调线程弹 tkinter 无焦点不可用
    （2026-11-09 vault 教训）与控制台 GBK 编码坑。用户取消/失败返回空串。"""
    if os.name != "nt":
        return ""
    import subprocess
    import tempfile
    out_file = os.path.join(tempfile.gettempdir(), f"yuanai_pick_{os.getpid()}.txt")
    try:
        os.remove(out_file)
    except OSError:
        pass
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms | Out-Null;"
        "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
        f"$d.Description = '{title}';"
        "if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {"
        # UTF8Encoding($false) = 无 BOM（Encoding.UTF8 自带 BOM，Python 按 utf-8
        # 读入会变成路径首字符 U+FEFF → 路径不再以盘符开头 → abspath 错拼 exe
        # 目录 → 「目录不存在」——2026-11-11 真机踩坑）
        f"[System.IO.File]::WriteAllText('{out_file}', $d.SelectedPath, "
        "([System.Text.UTF8Encoding]::new($false)))"
        "}"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps],
                       capture_output=True, timeout=300,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        return ""
    try:
        with open(out_file, "r", encoding="utf-8") as f:
            picked = f.read().strip().lstrip("﻿")  # 双保险：残留 BOM 也剥
        os.remove(out_file)
        return picked
    except OSError:
        return ""


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--pick" in argv:
        # 交互式选择目录（托盘菜单同款通道；CLI 联调用）
        picked = pick_directory("选择 Claude Code 的工作目录（代码仓库）")
        if not picked:
            print("已取消")
            return 1
        try:
            p = set_project_dir(picked)
        except ValueError as e:
            print(f"拒绝设置: {e}", file=sys.stderr)
            return 2
        print(f"已设置工作目录: {p}")
        return 0
    if "--clear" in argv:
        had = clear_project_dir()
        print("已清除工作目录配置" if had else "本来就没有配置")
        return 0
    if "--set" in argv:
        i = argv.index("--set")
        if i + 1 >= len(argv):
            print("用法: python -m agent.cc_workspace --set <目录>", file=sys.stderr)
            return 2
        try:
            p = set_project_dir(argv[i + 1])
        except ValueError as e:
            print(f"拒绝设置: {e}", file=sys.stderr)
            return 2
        print(f"已设置工作目录: {p}")
        info = describe()
        if not info["guard_ready"]:
            print(f"⚠ 安全钩子未就绪（spawn 仍会被拒绝）: {info['guard_reason']}")
        return 0
    info = describe()
    if "--json" in argv:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0
    print(f"工作目录: {info['project_dir']}")
    print(f"来源    : {info['source']}")
    print(f"配置文件: {info['config_file']}")
    print("钩子就绪: " + ("是" if info["guard_ready"] else f"否（{info['guard_reason']}）"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
