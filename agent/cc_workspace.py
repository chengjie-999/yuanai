"""CC 委派内建工作仓库（2026-11-08）：冻结 exe 下 CC_PROJECT_DIR 未设置时
自动初始化 %LOCALAPPDATA%\\XiaoYuanAI\\workspace——把打包内置的
claude_guard.py 钩子脚本与 .claude/settings.json 注册落地，
Claude Code 委派开箱即用（傻瓜设计：用户零配置零环境变量）。
设置 CC_PROJECT_DIR 指向真实仓库仍优先（老手可用）。

安全不变：guard 落地 + settings 注册是 guard_ready fail-closed 门禁的
前提，本模块只补「存在性」，不削弱任何校验。"""

import os
import shutil
import sys

WORKSPACE_NAME = "workspace"

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


def ensure_cc_workspace() -> str:
    """返回 CC 委派的工作仓库根：优先 CC_PROJECT_DIR（真实仓库）；
    冻结模式未设置 → 数据根下的内建 workspace（惰性初始化 guard 三件套）"""
    env_dir = os.getenv("CC_PROJECT_DIR", "")
    if env_dir and os.path.isdir(env_dir):
        return os.path.abspath(env_dir)
    if not getattr(sys, "frozen", False):
        # 源码模式：仓库根自带 scripts/hooks 与 .claude/settings.json
        from utils.data_path import root_path
        return root_path()
    from utils.data_path import frozen_data_root
    ws = os.path.join(frozen_data_root(), WORKSPACE_NAME)
    _init_workspace(ws)
    return ws


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
