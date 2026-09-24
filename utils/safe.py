"""输入安全工具 — 单点实现，全仓复用（安全加固 S0 引入）。

- safe_ident(name)：SQL 标识符白名单（表名/列名拼进 SQL 前必须过）
- safe_filename(name)：文件名白名单（basename + 字符集 + 去保留名）
- ensure_within(base, target)：realpath 包含校验（防路径穿越），不满足抛 ValueError
"""
import os
import re

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_FILENAME_RE = re.compile(r"^[A-Za-z0-9_一-鿿.\-]{1,128}$")
# 永不落盘的保留名（Windows 设备名等）
_RESERVED = {
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
}


def safe_ident(name: str) -> str:
    """SQL 标识符白名单（表名/列名拼进 SQL 前必须过）。
    不合法抛 ValueError，杜绝注入与意外字符。"""
    name = str(name or "").strip().strip("`")
    if not _IDENT_RE.match(name):
        raise ValueError(f"非法标识符: {name!r}（仅允许字母/数字/下划线，字母开头）")
    return name


def safe_filename(name: str) -> str:
    """文件名白名单：拒绝含路径成分（/ 或 \\）与保留名，字符集校验。
    不合法抛 ValueError（宁可拒绝也不静默改名，用户可见错误）。"""
    raw = str(name or "").strip()
    norm = raw.replace("\\", "/")
    if not raw:
        raise ValueError("文件名为空")
    if "/" in norm:
        raise ValueError(f"非法文件名（含路径成分）: {name!r}")
    base = raw.strip(".")
    if not base:
        raise ValueError("文件名为空")
    if not _FILENAME_RE.match(base):
        raise ValueError(f"非法文件名: {base!r}（仅允许中英文/数字/下划线/点/横线，≤128 字符）")
    if base.lower().split(".")[0] in _RESERVED:
        raise ValueError(f"非法文件名（系统保留名）: {base!r}")
    return base


def ensure_within(base: str, target: str) -> str:
    """realpath 包含校验：target 必须落在 base 内，否则抛 ValueError。返回 target 的 realpath。"""
    b = os.path.realpath(base)
    t = os.path.realpath(target)
    if not (t == b or t.startswith(b + os.sep)):
        raise ValueError(f"路径越界: {target!r} 不在 {base!r} 内")
    return t
