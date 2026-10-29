"""内容安全闸（C6 合规 v1，2026-10-29）——输入侧关键词拦截 + 审计留痕

定位：生成式 AI 办法第 4/14 条的最低可实现防线。v1 只做**输入侧**：
用户输入命中高危关键词 → 拒绝请求并返回合规提示（不进入模型）。
输出侧语义审核需接模型审核 API（豆包/火山内容安全），挂账下一批。

词库：内置基础集合 + data/safety_keywords.txt 每行一词（部署可扩展）。
"""

import logging
import os
import re

from utils.data_path import root_path

logger = logging.getLogger(__name__)

# 内置高危词（政治敏感/色情/暴力/违法类基础集合；只做高置信度拦截，
# 宁可漏检不误伤正常对话）
_BUILTIN_KEYWORDS = {
    "恐怖袭击", "制造炸弹", "炸弹制作", "枪支买卖", "毒品制作",
    "冰毒配方", "洗钱教程", "黑客攻击教程", "传播淫秽",
}

_EXTRA_LOADED = False
_KEYWORDS: set = set(_BUILTIN_KEYWORDS)


def _load_extra():
    global _EXTRA_LOADED
    if _EXTRA_LOADED:
        return
    _EXTRA_LOADED = True
    try:
        path = os.path.join(root_path(), "data", "safety_keywords.txt")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    w = line.strip()
                    if w and not w.startswith("#"):
                        _KEYWORDS.add(w)
    except Exception:
        pass


def check_content(text: str) -> tuple:
    """检查文本是否命中高危词。返回 (blocked: bool, hit_word: str)。
    词库为空或文本为空时不拦截。"""
    if not text or not text.strip():
        return False, ""
    _load_extra()
    if not _KEYWORDS:
        return False, ""
    for w in _KEYWORDS:
        if w in text:
            return True, w
    return False, ""


def audit_log(user_id: int, kind: str, hit: str, text_preview: str) -> None:
    """拦截审计（data/logs/content_safety.log；失败静默）"""
    import time
    try:
        path = os.path.join(root_path(), "data", "logs", "content_safety.log")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} uid={user_id} "
                    f"kind={kind} hit={hit} text={text_preview[:80]!r}\n")
    except Exception:
        pass


BLOCK_MESSAGE = "该请求包含违规内容，已按平台规则拒绝处理。如有疑问请联系管理员。"
