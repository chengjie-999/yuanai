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
from typing import Callable, Optional

from yuanai_core.core.schemas import AgentEvent, progress
from yuanai_core.rag import current_request_id
from utils.data_path import root_path

logger = logging.getLogger(__name__)

CLAUDE_CLI = "claude"
PROJECT_ROOT = root_path()
SUBPROCESS_TIMEOUT = 600       # 单次任务最长 10 分钟
HEARTBEAT_SECONDS = 30         # 心跳间隔（重置云端 SSE 300s 超时）
MAX_OUTPUT_CHARS = 8000        # tool_end 输出上限（进入 LLM 上下文与聊天记录）

_ALLOWED_TOOLS = "Read,Glob,Grep,Write,Edit,Bash"
_DISALLOWED_TOOLS = "WebFetch,WebSearch"

_BRIDGE_SYSTEM_PROMPT = (
    "你在以无头模式（非交互）为小元AI平台执行委派任务，无法与用户实时交互，"
    "遇到需要人工确认的操作时选择安全做法或说明原因。"
    "严格遵守以下安全规则（违反即任务失败）："
    "绝不执行 git push / git remote add/set-url / git reset --hard / git clean / rm -rf / rmdir /s / "
    "curl / wget / ssh / scp / rsync 等外联命令；绝不读取 ~/.ssh、~/.aws 等凭据文件或导出环境变量；"
    "绝不使用 sudo / runas 提权；绝不执行 npm install -g / pip install --user；"
    "绝不执行 shutdown / format / diskpart / taskkill /f 等系统命令；"
    "文件写入仅限本仓库目录内。git commit 可以做，但绝不推送。"
    "完成后用简洁中文总结：做了什么、改了哪些文件、如何验证。"
)

# 第三方网关模式（ANTHROPIC_BASE_URL 指向非官方地址，如 deepseek 网关）下
# Claude Code hooks 不注册，命令级拦截降级为提示词约束 + 进程级白名单
_IS_3P_MODE = bool(os.getenv("ANTHROPIC_BASE_URL")) and \
    "api.anthropic.com" not in os.getenv("ANTHROPIC_BASE_URL", "")


def _build_command(claude_path: str, prompt: str) -> list:
    return [
        claude_path, "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",  # stream-json 要求 --verbose
        "--permission-mode", "acceptEdits",
        "--allowedTools", _ALLOWED_TOOLS,
        "--disallowedTools", _DISALLOWED_TOOLS,
        "--setting-sources", "project",
        "--max-budget-usd", "10",
        "--append-system-prompt", _BRIDGE_SYSTEM_PROMPT,
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

    if _IS_3P_MODE:
        logger.warning("第三方网关模式（hooks 不可用）：命令级拦截降级为提示词约束 + 进程级白名单")

    cwd = cwd or PROJECT_ROOT
    cmd = _build_command(claude_path, prompt)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
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

    read_task = asyncio.create_task(_read_stdout())
    hb_task = asyncio.create_task(_heartbeat())
    try:
        try:
            await asyncio.wait_for(proc.wait(), SUBPROCESS_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return "Claude Code 执行超时（10 分钟），已终止"
        await read_task  # 排空剩余输出
    finally:
        hb_task.cancel()

    if error_text:
        _audit(prompt, proc.returncode, len(final_text), "error")
        return f"Claude Code 执行失败: {error_text}"[:MAX_OUTPUT_CHARS]

    if not final_text and proc.returncode != 0:
        assert proc.stderr is not None
        stderr_tail = (await proc.stderr.read()).decode("utf-8", errors="replace")[-500:]
        _audit(prompt, proc.returncode, 0, "exit_error")
        return f"Claude Code 异常退出（code={proc.returncode}）: {stderr_tail}"

    text = final_text.strip()
    if not text:
        _audit(prompt, proc.returncode, 0, "empty")
        return "Claude Code 未返回内容（可能被安全策略拒绝或会话异常）"
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[:MAX_OUTPUT_CHARS] + "\n...(输出过长已截断)"
    _audit(prompt, proc.returncode, len(text), "ok")
    return text


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
