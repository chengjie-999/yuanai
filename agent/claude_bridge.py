"""Claude Code 桥接进程：以独立 agent_id 连接云端 WS Hub，让云端聊天直接对话本机 Claude Code

与 agent/main.py（统筹 Agent）不同：本进程不跑统筹 LLM，而是把每个 chat_request
交给 headless Claude Code（stream-json 双向流），把输出流式映射回 WS 事件：
sender(agent) → token/reasoning → tool_start/tool_end → done

用法:
    python -m agent.claude_bridge --server-url wss://cjyuanai.cn \\
        --agent-id <claude专用账号user_id> --agent-token <长令牌>

依赖:
- 本机安装并登录 Claude Code CLI（claude）
- 云端 CLAUDE_BRIDGE_AGENT_ID 配置为本进程的 agent_id

说明（2026-08）:
- 会话持久化: data/claude_sessions.json（cloud session_id → claude session uuid）
- 审批流（review 级命令确认）依赖 claude-agent-sdk 的 can_use_tool；
  当前网络无法安装 SDK（pypi.org 不通、清华源无包），审批暂未启用，
  review 级命令由提示词黑名单约束（同 Phase 1 delegate）
"""

import argparse
import asyncio
import json
import logging
import os
import shutil
import signal
import socket
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.ws_client import AgentWSClient
from yuanai_core.core.schemas import (
    ChatRequest, AgentEvent,
    token as ev_token, reasoning as ev_reasoning, tool_start as ev_tool_start,
    tool_end as ev_tool_end, done as ev_done, error_event, progress, sender_event,
)
from utils.data_path import root_path

logger = logging.getLogger("claude_bridge")

PROJECT_ROOT = root_path()
SESSIONS_FILE = os.path.join(PROJECT_ROOT, "data", "claude_sessions.json")
HEARTBEAT_SECONDS = 30
MAX_TOOL_OUTPUT = 2000
CLAUDE_CLI = "claude"
BRIDGE_TIMEOUT = 900  # 单次会话最长 15 分钟

_ALLOWED_TOOLS = "Read,Glob,Grep,Write,Edit,Bash"
_DISALLOWED_TOOLS = "WebFetch,WebSearch"

_BRIDGE_SYSTEM_PROMPT = (
    "你在以无头模式（非交互）为小元AI平台执行任务，用户通过云端聊天与你对话。"
    "严格遵守以下安全规则（违反即任务失败）："
    "绝不执行 git push / git remote add/set-url / git reset --hard / git clean / rm -rf / rmdir /s / "
    "curl / wget / ssh / scp / rsync 等外联命令；绝不读取 ~/.ssh、~/.aws 等凭据文件或导出环境变量；"
    "绝不使用 sudo / runas 提权；绝不执行 npm install -g / pip install --user；"
    "绝不执行 shutdown / format / diskpart / taskkill /f 等系统命令；"
    "文件写入仅限本仓库目录内。git commit 可以做，但绝不推送。"
    "完成后用简洁中文总结：做了什么、改了哪些文件、如何验证。"
)


class SessionStore:
    """cloud session_id → claude session uuid 映射（单进程写，temp+rename）"""

    def __init__(self, path: str):
        self._path = path
        self._data = {}

    def load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            self._data = {}

    def get(self, cloud_sid: str):
        if not cloud_sid:
            return None
        entry = self._data.get(cloud_sid)
        return entry.get("claude_session_id") if entry else None

    def put(self, cloud_sid: str, claude_sid: str):
        if not cloud_sid or not claude_sid:
            return
        now = time.time()
        self._data[cloud_sid] = {"claude_session_id": claude_sid, "created": now, "updated": now}
        # 清理：>30 天未更新或超过 200 条
        self._data = {
            k: v for k, v in self._data.items()
            if now - float(v.get("updated", now)) < 30 * 86400
        }
        if len(self._data) > 200:
            for k in sorted(self._data, key=lambda k: self._data[k].get("updated", 0))[:len(self._data) - 200]:
                del self._data[k]
        self._save()

    def clear(self, cloud_sid: str):
        if cloud_sid in self._data:
            del self._data[cloud_sid]
            self._save()

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except Exception as e:
            logger.warning("会话映射保存失败: %s", e)


def _extract_prompt(req: ChatRequest) -> str:
    """取最后一条 user 消息文本（兼容 content 为 str 或文本块列表）"""
    for m in reversed(req.messages):
        if isinstance(m, dict) and m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                return "\n".join(parts)
    return ""


def _tool_result_content(result_block: dict) -> str:
    """提取 tool_result 文本（content 可能是 str 或 block 列表）"""
    content = result_block.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            c.get("text", "") for c in content
            if isinstance(c, dict) and c.get("type") == "text"
        )
    return str(content)


class ClaudeBridgeHandler:
    """把 chat_request 交给 headless Claude Code 并流式映射为 WS 事件"""

    def __init__(self, ws_send=None):
        self._ws_send = ws_send  # callable(event) fire-and-forget（心跳等旁路事件）
        self._sessions = SessionStore(SESSIONS_FILE)
        self._sessions.load()
        self._locks = {}  # cloud session_id -> asyncio.Lock（防并发 query）
        self._pending_approvals = {}  # decision_id -> asyncio.Future（SDK 审批流启用后使用）

    async def stream(self, req: ChatRequest) -> "asyncio.AsyncGenerator[AgentEvent, None]":
        rid = req.request_id

        # 审批决议（SDK 模式启用后走这里；当前恒空）
        if req.decision:
            decision_id = req.decision.get("decision_id", "")
            fut = self._pending_approvals.pop(decision_id, None)
            if fut and not fut.done():
                fut.set_result(bool(req.decision.get("approve")))
            yield ev_done("", "", rid)
            return

        prompt = _extract_prompt(req)
        if not prompt:
            yield ev_done("", "", rid)
            return

        lock_key = req.session_id or "global"
        lock = self._locks.setdefault(lock_key, asyncio.Lock())
        if lock.locked():
            yield error_event("Claude Code 正在处理上一请求，请稍候", rid)
            return
        async with lock:
            async for ev in self._run_query(req, rid, prompt):
                yield ev

    async def _run_query(self, req: ChatRequest, rid: str, prompt: str):
        claude_path = shutil.which(CLAUDE_CLI)
        if claude_path is None:
            yield error_event("本机未安装 Claude Code CLI（请先安装并登录 claude）", rid)
            return

        yield sender_event("claude", rid)

        resume_sid = self._sessions.get(req.session_id)
        claude_sid = resume_sid or str(uuid.uuid4())
        cmd = [
            claude_path, "-p", prompt,
            "--output-format", "stream-json", "--verbose",
            "--include-partial-messages",
            "--permission-mode", "acceptEdits",
            "--allowedTools", _ALLOWED_TOOLS,
            "--disallowedTools", _DISALLOWED_TOOLS,
            "--setting-sources", "project",
            "--max-budget-usd", "10",
            "--append-system-prompt", _BRIDGE_SYSTEM_PROMPT,
        ]
        # 已有会话用 --resume 续接；新会话用 --session-id 固定 UUID（--session-id 只用于新建）
        if resume_sid:
            cmd += ["--resume", resume_sid]
        else:
            cmd += ["--session-id", claude_sid]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(PROJECT_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "CLAUDE_CODE_BRIDGE": "1"},
        )

        tool_id_map = {}   # tool_use id -> tool name
        saw_delta = False  # 是否已收到流式 text_delta（用于 assistant 消息降级补发）
        final_result = ""
        final_session_id = claude_sid
        is_error = False
        result_obj = None  # 收到的 result 消息（未收到 = 进程异常退出）

        async def _heartbeat():
            elapsed = 0
            while proc.returncode is None:
                await asyncio.sleep(HEARTBEAT_SECONDS)
                if proc.returncode is None:
                    elapsed += HEARTBEAT_SECONDS
                    if self._ws_send:
                        self._ws_send(progress(0, 0, f"Claude Code 思考中（{elapsed}s）...", rid))

        hb_task = asyncio.create_task(_heartbeat())
        try:
            assert proc.stdout is not None
            async for raw in proc.stdout:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg_type = obj.get("type", "")

                if msg_type == "stream_event":
                    ev = obj.get("event", {})
                    if ev.get("type") == "content_block_delta":
                        delta = ev.get("delta", {})
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            saw_delta = True
                            yield ev_token(delta["text"], rid)
                        elif delta.get("type") == "thinking_delta" and delta.get("thinking"):
                            yield ev_reasoning(delta["thinking"], rid)

                elif msg_type == "assistant":
                    message = obj.get("message", {})
                    if message.get("parent_tool_use_id"):
                        continue  # 子 Agent 内部消息，不转发
                    blocks = message.get("content", [])
                    for b in blocks:
                        if b.get("type") == "tool_use":
                            name = b.get("name", "unknown")
                            tool_id_map[b.get("id", "")] = name
                            yield ev_tool_start(name, rid)
                        elif b.get("type") == "text" and not saw_delta:
                            # 无流式增量时降级补发完整文本
                            if b.get("text"):
                                yield ev_token(b["text"], rid)

                elif msg_type == "user":
                    message = obj.get("message", {})
                    if message.get("parent_tool_use_id"):
                        continue
                    for b in message.get("content", []):
                        if b.get("type") == "tool_result":
                            name = tool_id_map.get(b.get("tool_use_id", ""), "unknown")
                            output = _tool_result_content(b)
                            if b.get("is_error"):
                                output = f"[执行出错] {output}"
                            if len(output) > MAX_TOOL_OUTPUT:
                                output = output[:MAX_TOOL_OUTPUT] + "\n...(输出过长已截断)"
                            yield ev_tool_end(name, output, rid)

                elif msg_type == "result":
                    result_obj = obj
                    final_session_id = obj.get("session_id", claude_sid)
                    is_error = bool(obj.get("is_error"))
                    if not is_error:
                        final_result = obj.get("result", "")
                    else:
                        final_result = obj.get("result") or obj.get("subtype", "error")
        finally:
            hb_task.cancel()

        # 未收到 result 消息 = 进程异常退出
        if result_obj is None:
            stderr_tail = ""
            try:
                if proc.returncode is None:
                    await asyncio.wait_for(proc.wait(), 10)
                if proc.stderr:
                    stderr_tail = (await proc.stderr.read()).decode("utf-8", errors="replace")[-300:]
            except Exception:
                pass
            is_error = True
            final_result = f"Claude Code 进程异常退出（code={proc.returncode}）: {stderr_tail}"

        # 会话持久化
        if is_error or "error" in str((result_obj or {}).get("subtype", "")).lower():
            self._sessions.clear(req.session_id)
        else:
            self._sessions.put(req.session_id, final_session_id)

        if is_error:
            yield error_event(f"Claude Code 执行失败: {final_result[:500]}", rid)
        else:
            yield ev_done(final_result, "", rid)


def parse_args():
    p = argparse.ArgumentParser(description="小元AI Claude Code 桥接进程")
    p.add_argument("--server-url", default="wss://cjyuanai.cn", help="云端 WebSocket 地址")
    p.add_argument("--agent-id", default=socket.gethostname(), help="Agent 唯一标识（= 专属云账号 user_id）")
    p.add_argument("--agent-name", default="Claude Code 桥接", help="Agent 显示名称")
    p.add_argument("--agent-token", default=os.getenv("AGENT_TOKEN", ""), help="Agent 认证 JWT token（也可用 AGENT_TOKEN 环境变量）")
    return p.parse_args()


async def main():
    args = parse_args()

    from logging.handlers import RotatingFileHandler
    log_dir = os.path.join(PROJECT_ROOT, "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(
                os.path.join(log_dir, "claude_bridge.log"),
                maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
            ),
        ],
    )
    logging.getLogger("websockets").setLevel(logging.WARNING)

    # 启动预检
    if shutil.which(CLAUDE_CLI) is None:
        logger.error("未找到 Claude Code CLI（claude），请先安装并登录；桥接进程退出")
        return

    handler = ClaudeBridgeHandler()
    client = AgentWSClient(
        server_url=args.server_url,
        agent_id=args.agent_id,
        agent_name=args.agent_name,
        capabilities=["claude_code"],
        agent_token=args.agent_token,
    )
    handler._ws_send = client.send_event
    client.on_chat_request(handler.stream)

    logger.info("=" * 50)
    logger.info("Claude Code 桥接进程启动")
    logger.info("云端地址: %s | Agent ID: %s", args.server_url, args.agent_id)
    logger.info("会话映射: %s", SESSIONS_FILE)
    logger.info("=" * 50)

    loop = asyncio.get_running_loop()
    stop = loop.create_future()

    def _shutdown():
        logger.info("收到退出信号，正在关闭...")
        stop.set_result(True)

    _signal_ok = False
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
            _signal_ok = True
        except NotImplementedError:
            pass
    if not _signal_ok:
        # Windows fallback: signal.signal + call_soon_threadsafe
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda s, f: loop.call_soon_threadsafe(_shutdown))

    connect_task = asyncio.create_task(client.connect())
    try:
        await stop
    except asyncio.CancelledError:
        pass
    finally:
        await client.disconnect()
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass
    logger.info("Claude Code 桥接进程已退出")


if __name__ == "__main__":
    asyncio.run(main())
