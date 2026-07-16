"""Agent 工具自动发现 + 按 Agent 角色分配"""

import os
import logging
import importlib
from typing import List

from langchain_core.tools import BaseTool
from yuanai_core.tools import all_tools as shared_tools, load_tools_for

logger = logging.getLogger(__name__)


def _scan_agent_tools() -> List[BaseTool]:
    """扫描 agent/tools/ 目录，加载所有专用工具（不含共享工具）"""
    tools = []
    seen_names = set()
    base_dir = os.path.dirname(__file__)

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith('__') and not d.startswith('.'))
        for file in sorted(files):
            if file.endswith('.py') and not file.startswith('__'):
                rel_path = os.path.relpath(os.path.join(root, file), base_dir)
                module_path = rel_path[:-3].replace(os.sep, '.')
                module_name = f"agent.tools.{module_path}"

                try:
                    module = importlib.import_module(module_name)
                    for attr_name in sorted(dir(module)):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, BaseTool):
                            if attr.name not in seen_names:
                                seen_names.add(attr.name)
                                tools.append(attr)
                except Exception as e:
                    logger.warning("导入工具模块 %s 失败: %s", module_name, e)

    return tools


def load_agent_tools() -> List[BaseTool]:
    """全部工具 = 共享 + 专用（用于需要所有工具的 Agent，已弃用，保留兼容）"""
    tools = list(shared_tools)
    seen_names = {t.name for t in tools}
    for t in _scan_agent_tools():
        if t.name not in seen_names:
            seen_names.add(t.name)
            tools.append(t)
    logger.info("Agent 全部工具: %d 个（共享 %d + 专用 %d）",
                len(tools), len(shared_tools), len(tools) - len(shared_tools))
    return tools


def load_automation_tools() -> List[BaseTool]:
    """自动化 Agent 专用工具集：
    - 全部 38 个 agent/tools/ 专用工具（浏览器、审核、Cookie、截图）
    - 仅加载 memory + knowledge 共享工具（上下文相关）
    - 排除：计算器、天气、数据分析、爬取、文件、统计（与自动化无关）
    """
    # 只保留与自动化上下文相关的共享工具
    context_tools = load_tools_for("memory", "knowledge")
    tools = list(context_tools)
    seen_names = {t.name for t in tools}

    for t in _scan_agent_tools():
        if t.name not in seen_names:
            seen_names.add(t.name)
            tools.append(t)

    logger.info("自动化 Agent 工具: %d 个（上下文 %d + 专用 %d）",
                len(tools), len(context_tools), len(tools) - len(context_tools))
    return tools


# 模块级单例（保留兼容）
all_agent_tools = load_agent_tools()
# 自动化专用工具
automation_tools = load_automation_tools()


# ===================== 自动化 Agent 工具分组 =====================
# 按关键词匹配加载子集，节省 ~55% token

AUTOMATION_TOOL_GROUPS = {
    "browser": {
        "launch_new_browser", "close_browser",
        "get_website_info", "open_website_by_code", "open_website_by_name", "open_custom_url",
        "get_browser_status", "get_current_url",
        "refresh_page", "load_cookies", "save_cookies",
        "take_browser_screenshot",
        "cookies_to_requests", "cookies_to_header",
    },
    "audit": {
        "get_task_cards", "start_task", "go_home", "save_page_html",
        "get_question_info", "submit_task",
        "zoom_question", "restore_question_view",
        "mark_question_correct", "confirm_rejection",
        "scroll_canvas", "click_canvas",
        "load_page_cookies", "save_page_cookies",
        "get_page_status",
    },
    "monitor": {
        "take_screenshot", "list_monitors",
    },
    "knowledge": {
        "retrieve_annotation_spec", "retrieve_audit_steps",
        "save_audit_feedback", "get_important_examples",
        "get_audit_feedback", "get_recent_feedbacks",
        "analyze_audit_errors",
    },
}

AUTOMATION_INTENT_KEYWORDS = {
    "browser":   {"打开", "启动", "关闭", "浏览器", "网页", "网站", "刷新",
                  "cookie", "登录", "browser", "launch", "open", "close",
                  "chrome", "页面", "导航"},
    "audit":     {"审核", "题目", "任务", "提交", "驳回", "标记", "标注",
                  "评分", "批改", "audit", "review", "question", "mark",
                  "submit", "小猿", "众包", "canvas", "画布"},
    "monitor":   {"截图", "屏幕", "显示器", "monitor", "screenshot", "截屏"},
    "knowledge": {"规范", "步骤", "反馈", "错误分析", "案例", "参考",
                  "knowledge", "feedback", "spec", "annotation"},
}


def classify_automation_intent(message: str) -> List[str]:
    """关键词匹配 → 返回应加载的工具组列表。空则返回全部组。"""
    matched = []
    for group, keywords in AUTOMATION_INTENT_KEYWORDS.items():
        if any(kw in message for kw in keywords):
            matched.append(group)
    return matched if matched else list(AUTOMATION_TOOL_GROUPS.keys())


def load_automation_tools_for_intent(intent_groups: List[str]) -> List[BaseTool]:
    """按意图组加载工具子集。"""
    from yuanai_core.tools import load_tools_for

    # 始终加载上下文工具
    tools = list(load_tools_for("memory", "knowledge"))
    seen_names = {t.name for t in tools}

    # 加载匹配组的专用工具
    all_agent = _scan_agent_tools()
    selected = set()
    for group in intent_groups:
        selected |= AUTOMATION_TOOL_GROUPS.get(group, set())

    for t in all_agent:
        if t.name in selected and t.name not in seen_names:
            seen_names.add(t.name)
            tools.append(t)

    logger.debug("按意图组 %s 加载 %d 个工具", intent_groups, len(tools))
    return tools
