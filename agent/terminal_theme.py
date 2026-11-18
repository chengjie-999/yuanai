# -*- coding: utf-8 -*-
"""终端主题（T2 品牌对齐，2026-11-18）。

明暗跟随链：云端 `/api/v1/agent/my-theme`（设备凭据 → 绑定用户的
`users.theme`，与网站 ThemeContext 同一列——网站改主题终端下次启动跟随，
终端 `/theme` 回写后网站登录时同步）→ `data/theme.json` 本地缓存
（云端不可达时的持久层）→ `TERMINAL_DARK` 环境变量（v3 遗留兼容）→
默认暗色。
"""
import json
import os

from utils.data_path import root_path

_THEME_FILE = os.path.join(root_path(), "data", "theme.json")
_VALID = ("light", "dark")


def _read_json() -> dict:
    try:
        with open(_THEME_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def read_theme_cache() -> str:
    """本地缓存主题；无效/缺失 → ''（调用方继续走降级链）"""
    theme = str(_read_json().get("theme", ""))
    return theme if theme in _VALID else ""


def write_theme_cache(theme: str) -> None:
    """写缓存（原子替换 tmp + os.replace；失败静默——缓存层不允许拖垮启动）"""
    try:
        os.makedirs(os.path.dirname(_THEME_FILE), exist_ok=True)
        tmp = _THEME_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"theme": theme}, f, ensure_ascii=False)
        os.replace(tmp, _THEME_FILE)
    except OSError:
        pass


def fetch_cloud_theme(timeout: float = 3.0) -> str | None:
    """云端主题（设备凭据）；任何失败（无身份/未绑定/网络）→ None 静默"""
    from yuanai_core.pure.agent_remote import agent_http
    try:
        r = agent_http("/my-theme", "GET", timeout=timeout)
        theme = str((r or {}).get("theme", ""))
        return theme if theme in _VALID else None
    except Exception:
        return None


def push_cloud_theme(theme: str, timeout: float = 3.0) -> bool:
    """主题回写云端（网站同列互同步）；失败静默返回 False（本地缓存已生效）"""
    from yuanai_core.pure.agent_remote import agent_http
    try:
        r = agent_http("/my-theme", "PUT", {"theme": theme}, timeout=timeout)
        return bool(r.get("ok"))
    except Exception:
        return False


def resolve_startup_theme() -> str:
    """启动主题：云端（成功即回写缓存）→ 本地缓存 → TERMINAL_DARK 环境
    （v3 遗留兼容）→ 默认暗色"""
    cloud = fetch_cloud_theme()
    if cloud:
        write_theme_cache(cloud)
        return cloud
    cached = read_theme_cache()
    if cached:
        return cached
    env = os.getenv("TERMINAL_DARK", "")
    if env in ("0", "1"):
        return "light" if env == "0" else "dark"
    return "dark"


def set_theme_synced(theme: str) -> str:
    """/theme 命令：写本地缓存 + 回推云端。返回实际生效主题（light/dark）"""
    if theme not in _VALID:
        theme = "dark"
    write_theme_cache(theme)
    push_cloud_theme(theme)
    return theme
