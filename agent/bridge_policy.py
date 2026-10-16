"""Claude Code 桥接安全策略：工具调用分类（allow / deny / review）

Phase 1（CLI 子进程）：review 由钩子直接拒绝（无审批通道）
Phase 2（SDK 桥接）：review 走云端聊天审批流（can_use_tool）

钩子与 SDK can_use_tool 共用本模块，保证两阶段安全口径一致。
"""

import json
import os
import re
from pathlib import Path

from utils.data_path import root_path

PROJECT_ROOT = Path(root_path()).resolve()

# 允许 curl/wget 访问本机回环地址（默认关闭，测试场景可设 CLAUDE_ALLOW_LOCALHOST=1）
ALLOW_LOCALHOST = os.getenv("CLAUDE_ALLOW_LOCALHOST", "0") == "1"

# ——— Bash 命令拒绝清单 ———
_BASH_DENY = [
    (r"\brm\s+-rf", "递归删除被禁止（如需删除请指定精确文件路径逐个删除）"),
    (r"\brmdir\s+/s", "递归删除目录被禁止"),
    (r"Remove-Item\b.*-Recurse", "PowerShell 递归删除被禁止"),
    (r"\bformat\b", "磁盘格式化被禁止"),
    (r"\bdiskpart\b", "磁盘分区操作被禁止"),
    (r"\bshutdown\b", "关机/重启被禁止"),
    (r"\bchkdsk\b", "磁盘检查被禁止"),
    (r"\btaskkill\s+/f", "强制结束进程被禁止"),
    (r"\bgit\s+push\b", "git push 被禁止（云端账号未授权推送代码）"),
    (r"\bgit\s+remote\s+(add|set-url|remove)", "修改 git 远程地址被禁止（防代码投递）"),
    (r"\bgit\s+reset\s+--hard", "git reset --hard 会丢弃改动，被禁止"),
    (r"\bgit\s+clean\b", "git clean 会删除未跟踪文件，被禁止"),
    (r"\bgit\s+checkout\s+--", "git checkout -- 会丢弃改动，被禁止"),
    (r"\bsudo\b", "sudo 提权被禁止"),
    (r"\brunas\b", "runas 提权被禁止"),
    (r"\bchmod\s+\S*7\S*", "chmod 777 类权限放开被禁止"),
    (r"\bicacls\b.*(/grant|/deny)", "icacls 权限修改被禁止"),
    (r"\bssh\b", "ssh 外联被禁止"),
    (r"\bscp\b", "scp 外传文件被禁止"),
    (r"\bsftp\b", "sftp 外传文件被禁止"),
    (r"\brsync\b", "rsync 外传文件被禁止"),
    (r"\bnc\b|\bncat\b|\btelnet\b", "网络通道工具被禁止"),
    (r"\bftp\b", "ftp 外传文件被禁止"),
    (r"Invoke-(WebRequest|RestMethod)\b", "PowerShell 外联下载被禁止"),
    (r"\biwr\b", "PowerShell 外联下载被禁止"),
    (r"Start-BitsTransfer\b", "PowerShell 外联下载被禁止"),
    (r"\.ssh", "读取 SSH 凭据被禁止"),
    (r"\.aws", "读取 AWS 凭据被禁止"),
    (r"\.gitconfig", "读取全局 git 配置被禁止"),
    (r"\.npmrc", "读取 npm 凭据文件被禁止"),
    (r"\bprintenv\b", "整段导出环境变量被禁止"),
    (r"\benv\s*(\||$)", "整段导出环境变量被禁止"),
    (r"/etc/passwd|/etc/shadow", "读取系统账户文件被禁止"),
    (r"\bnpm\s+install\s+-g", "全局安装 npm 包被禁止"),
    (r"\bpip\s+install\s+--user", "用户级 pip 安装被禁止"),
]

# ——— review 级（Phase 2 云端审批；Phase 1 钩子直接拒绝）———
_BASH_REVIEW = [
    (r"\bgit\s+commit\b", "git commit 需云端审批确认"),
]

# ==================== S0.1 修复：fail-closed 门禁 + Bash 白名单 ====================
# 背景：hooks 在 -p 无头模式实测不触发（第三方网关模式，见 CLAUDE.md），
# 因此不能只依赖钩子。三层防线：① 钩子注册（交互会话可用）② guard_ready 门禁
# ③ --allowedTools 移除裸 Bash（不依赖任何运行时行为）。

_BASE_TOOLS = "Read,Glob,Grep,Write,Edit,TodoWrite"  # TodoWrite = CC 制定/跟踪计划
# 只读/测试类常用命令白名单（Bash(前缀:*) 语法）
# 白名单放宽原则：桥接只服务白名单用户名（CLAUDE_BRIDGE_ALLOWED_USERNAMES），
# 且黑名单（外联/提权/破坏性命令）仍在提示词与钩子层拦截；
# 覆盖日常开发闭环：查看/编辑/测试/运行/提交（提交不推送）
_DEFAULT_BASH_ALLOW = [
    "Bash(git status:*)",
    "Bash(git diff:*)",
    "Bash(git log:*)",
    "Bash(git add:*)",
    "Bash(git commit:*)",
    "Bash(python -m pytest:*)",
    "Bash(python -m py_compile:*)",
    "Bash(python -m:*)",
    "Bash(python:*)",
    "Bash(ls:*)",
    "Bash(cat:*)",
    "Bash(pwd:*)",
    "Bash(mkdir:*)",
    "Bash(cp:*)",
    "Bash(mv:*)",
    "Bash(node:*)",
    "Bash(npm run:*)",
    "Bash(npx:*)",
]


def build_allowed_tools() -> str:
    """构造 --allowedTools：默认不含裸 Bash（即使钩子完全不生效也拦得住）。
    - CLAUDE_BRIDGE_ENABLE_BASH=0 → 纯只读+编辑（钩子探针未通过时的保守默认）
    - CLAUDE_BRIDGE_BASH_UNRESTRICTED=1 → 恢复裸 Bash（逃生舱，已知风险）
    """
    if os.getenv("CLAUDE_BRIDGE_BASH_UNRESTRICTED", "0") == "1":
        return _BASE_TOOLS + ",Bash"
    if os.getenv("CLAUDE_BRIDGE_ENABLE_BASH", "1") == "0":
        return _BASE_TOOLS
    return _BASE_TOOLS + "," + ",".join(_DEFAULT_BASH_ALLOW)


def guard_ready(project_root: str) -> tuple:
    """fail-closed 门禁：hook 脚本存在 + settings.json 已注册 + JSON 可解析。
    返回 (ok: bool, reason: str)。未就绪时调用方必须拒绝 spawn 子进程。"""
    root = Path(project_root)
    guard = root / "scripts" / "hooks" / "claude_guard.py"
    if not guard.is_file():
        return False, "hook 脚本缺失: scripts/hooks/claude_guard.py"
    settings = root / ".claude" / "settings.json"
    if not settings.is_file():
        return False, ".claude/settings.json 不存在（安全钩子未注册）"
    try:
        data = json.loads(settings.read_text("utf-8"))
    except Exception as e:
        return False, f".claude/settings.json 解析失败: {e}"
    for rule in (data.get("hooks") or {}).get("PreToolUse") or []:
        for h in rule.get("hooks", []):
            if "claude_guard.py" in str(h.get("command", "")):
                return True, ""
    return False, ".claude/settings.json 未注册 claude_guard.py 钩子"

_CURL_WGET = re.compile(r"\b(curl|wget)\b")
_LOCALHOST = re.compile(r"localhost|127\.0\.0\.1")


def classify_command(command: str):
    """分类 Bash 命令，返回 (verdict, reason)；verdict ∈ allow|deny|review"""
    cmd = command or ""
    if _CURL_WGET.search(cmd):
        if not (ALLOW_LOCALHOST and _LOCALHOST.search(cmd)):
            return "deny", "curl/wget 外联下载被禁止（防止本机数据外传）"
    for pattern, reason in _BASH_DENY:
        if re.search(pattern, cmd, re.IGNORECASE):
            return "deny", reason
    for pattern, reason in _BASH_REVIEW:
        if re.search(pattern, cmd, re.IGNORECASE):
            return "review", reason
    return "allow", ""


def _is_within(path: Path, root: Path) -> bool:
    """兼容 Python 3.8 的路径包含检查（is_relative_to 需 3.9+）"""
    p = str(path.resolve()).replace("\\", "/").rstrip("/")
    r = str(root).replace("\\", "/").rstrip("/")
    # Windows 路径大小写不敏感，统一 casefold 比较
    return p.casefold() == r.casefold() or p.casefold().startswith(r.casefold() + "/")


def _path_within_root(tool_input: dict) -> bool:
    """Write/Edit 的目标路径必须位于项目仓库内"""
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not path:
        return True
    p = Path(str(path))
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    try:
        return _is_within(p, PROJECT_ROOT)
    except Exception:
        return False


def classify(tool_name: str, tool_input: dict) -> str:
    """工具调用分类入口：返回 allow | deny | review

    名字兼容两套：CLI 白名单名（Write/Edit/Bash）与 anthropic SDK 内置工具名
    （str_replace_based_edit_tool / bash——内置声明 schema-less，输入形状不同）。
    """
    # SDK 内置 text editor：所有 command（view/create/str_replace/insert）都动文件，
    # 统一按写入语义做路径校验
    if tool_name == "str_replace_based_edit_tool":
        return "allow" if _path_within_root(tool_input) else "deny"
    if tool_name in ("Write", "Edit"):
        return "allow" if _path_within_root(tool_input) else "deny"
    if tool_name in ("Bash", "bash"):
        command = str(tool_input.get("command", ""))
        if str(tool_input.get("restart")) in ("true", "True", "1"):
            return "deny"  # SDK 会话重启请求不执行（无状态执行器）
        verdict, _ = classify_command(command)
        return verdict
    return "allow"  # Read/Glob/Grep 等只读工具放行


def explain(tool_name: str, tool_input: dict) -> str:
    """拒绝/审批时的原因说明"""
    if tool_name in ("Write", "Edit", "str_replace_based_edit_tool"):
        if not _path_within_root(tool_input):
            return "写入路径超出项目仓库目录，被安全策略拒绝"
        return ""
    if tool_name in ("Bash", "bash"):
        _, reason = classify_command(str(tool_input.get("command", "")))
        return reason
    return ""
