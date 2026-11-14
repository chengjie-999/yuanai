"""delegate_to_claude_agent 工具：调用本机 Claude Code CLI（headless）完成代码/终端任务。

安全边界：
- cwd 锁定项目仓库根目录
- --permission-mode acceptEdits + 工具白名单 + 仓库内 PreToolUse 钩子拒绝危险命令
- 非交互模式无人工审批，危险操作由钩子直接拒绝
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
from typing import Callable, Optional

from yuanai_core.core.schemas import AgentEvent, progress
from yuanai_core.rag import current_request_id
from agent.bridge_policy import (build_allowed_tools, guard_ready,
                                 register_spawned_proc, unregister_spawned_proc)

logger = logging.getLogger(__name__)

CLAUDE_CLI = "claude"
# 冻结版仓库目录解析（2026-10-19 初版 + 2026-11-08 傻瓜化 + 2026-11 可配置）：
# exe 内 root_path() 指向数据目录而非真实仓库，其中没有 scripts/hooks 与
# .claude/settings.json → guard_ready 永远 fail-closed、Claude 委派不可用。
# 现方案：选择链见 agent/cc_workspace.resolve_project_dir（CC_PROJECT_DIR >
# 数据根 cc_config.json > 源码根 / 内建 workspace）——用户零配置，门禁不削弱。
from agent.cc_workspace import resolve_project_dir


def _project_root() -> str:
    """每次委派重新解析：运行期切换工作目录后，下一次即生效"""
    return resolve_project_dir()


PROJECT_ROOT = resolve_project_dir()
SUBPROCESS_TIMEOUT = 600       # 单次任务最长 10 分钟
HEARTBEAT_SECONDS = 30         # 心跳间隔（重置云端 SSE 300s 超时）
MAX_OUTPUT_CHARS = 8000        # tool_end 输出上限（进入 LLM 上下文与聊天记录）

_DISALLOWED_TOOLS = "WebFetch,WebSearch"
# 委派静默化（P0）：Windows 下不弹空控制台窗口（0x08000000）；非 Windows 无此概念
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
_STDERR_TAIL = 2000  # 失败时带回 stderr 末尾字数（失败不再无日志）

# 提示词优化（2026-11-14）：桥接提示统一为 claude_loop.bridge_system_prompt()
# 单一事实源（安全规则 + cc_search 通道 + claude_code.md 身份卡 + 环境自述）——
# 此前本文件维护一份分叉版本（无 TodoWrite/【记住】协议，有 cc_search/身份卡），
# 两链路能力描述不一致；现删除本地定义，与终端 /claude、云端桥接共用一份

# 第三方网关模式（ANTHROPIC_BASE_URL 指向非官方地址，如 deepseek 网关）下
# Claude Code hooks 不注册，命令级拦截降级为提示词约束 + 进程级白名单
_IS_3P_MODE = bool(os.getenv("ANTHROPIC_BASE_URL")) and \
    "api.anthropic.com" not in os.getenv("ANTHROPIC_BASE_URL", "")


def _build_command(claude_path: str, prompt: str) -> list:
    # P3-1 环境自述：工作目录/shell/文件工具边界随每次调用重新解析
    from agent.claude_loop import bridge_system_prompt
    return [
        claude_path, "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",  # stream-json 要求 --verbose
        "--permission-mode", "acceptEdits",
        "--allowedTools", build_allowed_tools(),
        "--disallowedTools", _DISALLOWED_TOOLS,
        "--setting-sources", "project",
        "--max-budget-usd", "10",
        "--append-system-prompt", bridge_system_prompt(),
    ]


async def run_claude_once(
    prompt: str,
    request_id: str = "",
    emit: Optional[Callable[[AgentEvent], None]] = None,
    cwd: Optional[str] = None,
) -> str:
    """执行一次 headless Claude Code 调用，返回最终文本。emit(event) 用于进度心跳。"""
    claude_path = shutil.which(CLAUDE_CLI)
    if claude_path is None:
        return "本机未安装 Claude Code CLI（请先安装并登录 claude）"

    # fail-closed 门禁：安全钩子未就绪绝不 spawn 子进程（S0.1 C1 修复）
    root = _project_root()
    ok, reason = guard_ready(root)
    if not ok:
        logger.error("拒绝启动 Claude Code：%s", reason)
        return f"安全钩子未就绪，已拒绝启动 Claude Code：{reason}"

    if _IS_3P_MODE:
        logger.warning("第三方网关模式（hooks 可能不触发）：命令级拦截靠进程级白名单兜底")

    cwd = cwd or root
    cmd = _build_command(claude_path, prompt)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=_NO_WINDOW,  # 委派静默化：不再每次弹空终端窗口
        env={
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "CLAUDE_CODE_BRIDGE": "1",  # 激活仓库内安全钩子（claude_guard.py）
        },
    )

    final_text = ""
    error_text = ""

    async def _read_stdout():
        """逐行解析 stream-json，只取 result 消息的最终结果"""
        nonlocal final_text, error_text
        assert proc.stdout is not None
        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "result":
                if obj.get("subtype") == "success":
                    final_text = obj.get("result") or ""
                else:
                    error_text = f"{obj.get('subtype', 'error')}: {obj.get('result', '')}"

    async def _heartbeat():
        """长任务期间周期发送 progress 事件，重置云端 SSE 300s 超时"""
        elapsed = 0
        while proc.returncode is None:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            if proc.returncode is None:
                elapsed += HEARTBEAT_SECONDS
                if emit and request_id:
                    emit(progress(0, 0, f"Claude Code 执行中（{elapsed}s）...", request_id))

    stderr_buf = ""  # 滚动保留 stderr 尾部——失败时带回返回（不再静默丢弃）

    async def _drain_stderr():
        # 2026-10-19 修复：stderr=PIPE 从不排水——verbose 模式输出多时管道写满，
        # 子进程阻塞直到超时才被 kill；并发排空并滚动保留末 _STDERR_TAIL 字
        nonlocal stderr_buf
        assert proc.stderr is not None
        try:
            async for chunk in proc.stderr:
                stderr_buf += chunk.decode("utf-8", errors="replace")
                if len(stderr_buf) > _STDERR_TAIL * 2:
                    stderr_buf = stderr_buf[-_STDERR_TAIL:]
        except Exception:
            pass

    register_spawned_proc(proc)  # P0 退出清子进程：托盘退出时 tree-kill
    read_task = asyncio.create_task(_read_stdout())
    err_task = asyncio.create_task(_drain_stderr())
    hb_task = asyncio.create_task(_heartbeat())
    try:
        try:
            await asyncio.wait_for(proc.wait(), SUBPROCESS_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            # P3-2 委派失败人话：超时带可行动指引（拆分任务重试）
            return _with_stderr("Claude Code 执行超时（10 分钟），已终止——"
                                "任务可能过重，建议拆分成小步骤后重试", stderr_buf)
        await read_task  # 排空剩余输出
    finally:
        hb_task.cancel()
        err_task.cancel()
        unregister_spawned_proc(proc)

    if error_text:
        _audit(prompt, proc.returncode, len(final_text), "error")
        return _with_stderr(f"Claude Code 执行失败: {error_text}——"
                            "如因安全策略被拒请调整任务描述；网络/网关问题可稍后重试", stderr_buf)

    if not final_text and proc.returncode != 0:
        _audit(prompt, proc.returncode, 0, "exit_error")
        return _with_stderr(f"Claude Code 异常退出（code={proc.returncode}）——"
                            "可稍后重试；若持续失败请检查本机 claude 安装", stderr_buf)

    text = final_text.strip()
    if not text:
        _audit(prompt, proc.returncode, 0, "empty")
        return "Claude Code 未返回内容（可能被安全策略拒绝或会话异常）"
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[:MAX_OUTPUT_CHARS] + "\n...(输出过长已截断)"
    _audit(prompt, proc.returncode, len(text), "ok")
    return text


def _with_stderr(msg: str, stderr_buf: str) -> str:
    """失败消息附 stderr 尾部（P0 委派静默化：失败不再无日志），并遵守输出上限"""
    tail = (stderr_buf or "").strip()[-_STDERR_TAIL:]
    if tail:
        msg = f"{msg}\n[stderr] {tail}"
    return msg[:MAX_OUTPUT_CHARS]


def _audit(prompt: str, exit_code, result_len: int, status: str):
    """委派调用审计（hooks 在第三方网关模式下不可用，此处兜底记录）"""
    import time
    try:
        log_path = os.path.join(PROJECT_ROOT, "data", "logs", "claude_audit.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} | DELEGATE | {status} | "
                f"exit={exit_code} | result_len={result_len} | {prompt[:200]}\n"
            )
    except Exception:
        pass


def make_claude_tool(emit: Optional[Callable[[AgentEvent], None]] = None):
    """创建 delegate_to_claude_agent 异步工具（供统筹 Agent 按意图动态加载）"""
    from langchain_core.tools import StructuredTool

    async def delegate_to_claude_agent(prompt: str) -> str:
        return await run_claude_once(prompt, current_request_id.get(), emit)

    return StructuredTool.from_function(
        coroutine=delegate_to_claude_agent,
        name="delegate_to_claude_agent",
        description=(
            "把需要在本机仓库编写/修改代码、执行终端命令、运行测试、Git 操作（commit/log/diff 等；"
            "push 会被安全策略拦截）的任务交给本机 Claude Code 完成。"
            "当用户要求写代码、改代码、修复 bug、重构、实现功能、跑命令、在本地项目创建文件时调用。"
            "参数 prompt: 详细任务描述（包含文件路径与验证方式）。"
        ),
    )
