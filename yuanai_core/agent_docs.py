# -*- coding: utf-8 -*-
"""智能体能力边界文档加载器（2026-10-19 起：模仿 CLAUDE.md 给每个智能体一份
「身份卡」，注入各自 system prompt——让智能体了解自己的能力与边界，完善记忆体系）

单一事实源：docs/agents/{name}.md（人工维护，改文档即改智能体自我认知）。
dev 环境从仓库读；PyInstaller 冻结环境从打包数据目录读（spec datas 已带）。
读取失败一律返回 ""（文档缺失不得破坏提示词构建）。
"""

import os
import sys

from utils.data_path import root_path


def agent_doc(name: str) -> str:
    """读取 docs/agents/{name}.md 全文（去首尾空白）；不存在返回 ''"""
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(sys._MEIPASS, "docs", "agents", f"{name}.md"))  # type: ignore[attr-defined]
    candidates.append(os.path.join(root_path(), "docs", "agents", f"{name}.md"))
    for p in candidates:
        try:
            with open(p, "r", encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            continue
    return ""
