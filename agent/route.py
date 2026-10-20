# -*- coding: utf-8 -*-
"""聊天请求三路分派（2026-10-21 清洁8：main.py 命令行模式与 tray.py 托盘模式共用，
此前两份 route() 各写一遍——托盘开关修复只改了托盘那份，行为漂移）

分派链：mode/target=claude → Claude Code 桥接；target=automation → 直调
automation Agent（确定性路由，跳过统筹 LLM）；其余 → 统筹 Orchestrator。

claude_enabled 回调供托盘模式实时读开关（关闭时回统筹并如实说明）；
命令行模式不传（恒可用）。
"""

from typing import Callable, Optional

# 融合后仅 automation 保留 @定向（分析/采集脚本类已工具化并入统筹）
TARGET_SKILLS = ("automation",)


def make_route(orchestrator, claude_handler,
               claude_enabled: Optional[Callable[[], bool]] = None):
    async def route(req):
        target = getattr(req, "target_agent", "") or ""
        if getattr(req, "mode", "") == "claude" or target == "claude":
            # 2026-10-19 修复：托盘开关关闭 Claude Code 时桥接分支仍无条件生效——
            # 开关失效；关闭时回统筹并如实说明
            if claude_enabled and not claude_enabled():
                from yuanai_core.core.schemas import done as _ev_done
                yield _ev_done("Claude Code 已在托盘菜单中停用。如需使用，请在托盘「Agent 开关」里启用后重试。",
                               "", req.request_id)
                return
            async for ev in claude_handler.stream(req):
                yield ev
        elif target in TARGET_SKILLS:
            async for ev in orchestrator.stream_target(req, target):
                yield ev
        else:
            async for ev in orchestrator.stream(req):
                yield ev

    return route
