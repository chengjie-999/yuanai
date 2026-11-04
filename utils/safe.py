"""输入安全工具 — 单点实现，全仓复用（安全加固 S0 引入）。

- safe_ident(name)：SQL 标识符白名单（表名/列名拼进 SQL 前必须过）
- safe_filename(name)：文件名白名单（basename + 字符集 + 去保留名）
- ensure_within(base, target)：realpath 包含校验（防路径穿越），不满足抛 ValueError
- resolve_within(path, base)：外部路径归一化为 base 下相对路径（V1-1 云边共用口径）
- normalize_save_filename(name, base)：写工具文件名归一化（剥离合法目录前缀）
- verified_write(path, content)：写后回读校验，不一致抛 IOError（V1-1）
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


# —— V1-1 写入-回读校验层（2026-11-05）——
# 云边共用同一份路径口径：本地 Agent 与云端进程此前各自解释「路径成分」，
# 曾致 save_data_csv 本地能跑云端报「非法文件名」、read_data_file 双重拼接读不回。
# 写/读工具一律经 resolve_within 归一，行为由本文件单点决定。

_SAVE_ALLOW_PREFIX = {"data", "file", "csv"}


def resolve_within(path: str, base: str) -> str:
    """外部路径归一化为 base 下的相对路径（云边共用）。

    - 相对路径：去空段/`.`，含 `..` 一律拒绝（防穿越）
    - 绝对路径（含 Windows 盘符）：realpath 必须落在 base 内，返回相对部分
    任何越界抛 ValueError。目标文件可不存在（写场景）。
    """
    raw = str(path or "").strip().strip('"').strip("'").replace("\\", "/")
    if not raw:
        raise ValueError("路径为空")
    base_real = os.path.realpath(base)
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        t = os.path.realpath(raw)
        if not (t == base_real or t.startswith(base_real + os.sep)):
            raise ValueError(f"路径越界: {path!r}")
        raw = t[len(base_real) + 1:] if t != base_real else ""
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ValueError(f"非法路径（含穿越成分）: {path!r}")
    return "/".join(parts)


def normalize_save_filename(name: str, base: str) -> str:
    """写工具文件名归一化：剥离模型常带的合法目录前缀（data/file/csv/…），
    拒绝穿越与未知路径成分，返回 base 下的纯文件名。

    - '报表.csv' / 'data/file/csv/报表.csv' / 'csv/报表.csv' → '报表.csv'
    - '../x.csv'（穿越）、'a/b.csv'（未知成分）→ ValueError（云边同一错误）
    """
    rel = resolve_within(name, base)
    if not rel:
        raise ValueError("文件名为空")
    parts = rel.split("/")
    i = 0
    while i < len(parts) - 1 and parts[i].lower() in _SAVE_ALLOW_PREFIX:
        i += 1
    if i != len(parts) - 1:
        raise ValueError(f"非法文件名（含路径成分）: {name!r}")
    return safe_filename(parts[-1])


def verified_write(path: str, content: str, encoding: str = "utf-8-sig") -> None:
    """写后回读校验：写入后立即读回比对，不一致抛 IOError（上游工具收到异常）。

    utf-8-sig 写入补 BOM、读取剥 BOM，回读与原文等价。
    """
    with open(path, "w", encoding=encoding) as f:
        f.write(content)
    with open(path, "r", encoding=encoding) as f:
        back = f.read()
    if back != content:
        raise IOError(f"写入校验失败（回读不一致）: {path}")
