"""Claude Code 桥接安全策略：工具调用分类（allow / deny / review）

Phase 1（CLI 子进程）：review 由钩子直接拒绝（无审批通道）
Phase 2（SDK 桥接）：review 走云端聊天审批流（can_use_tool）

钩子与 SDK can_use_tool 共用本模块，保证两阶段安全口径一致。
"""

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
    """工具调用分类入口：返回 allow | deny | review"""
    if tool_name in ("Write", "Edit"):
        return "allow" if _path_within_root(tool_input) else "deny"
    if tool_name == "Bash":
        verdict, _ = classify_command(str(tool_input.get("command", "")))
        return verdict
    return "allow"  # Read/Glob/Grep 等只读工具放行


def explain(tool_name: str, tool_input: dict) -> str:
    """拒绝/审批时的原因说明"""
    if tool_name in ("Write", "Edit"):
        if not _path_within_root(tool_input):
            return "写入路径超出项目仓库目录，被安全策略拒绝"
        return ""
    if tool_name == "Bash":
        _, reason = classify_command(str(tool_input.get("command", "")))
        return reason
    return ""
