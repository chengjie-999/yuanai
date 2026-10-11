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
from agent.bridge_policy import build_allowed_tools, guard_ready

logger = logging.getLogger("claude_bridge")

PROJECT_ROOT = root_path()
SESSIONS_FILE = os.path.join(PROJECT_ROOT, "data", "claude_sessions.json")
HEARTBEAT_SECONDS = 30
MAX_TOOL_OUTPUT = 2000
CLAUDE_CLI = "claude"
BRIDGE_TIMEOUT = 900  # 单次会话最长 15 分钟

_DISALLOWED_TOOLS = "WebFetch,WebSearch"

_BRIDGE_SYSTEM_PROMPT = (
    "你正运行在用户本机（本地 Claude Code 模式），身份是 Claude Code 本机助手，"
    "不是小元AI的统筹 Agent——自我介绍时说明你是本机 Claude Code。"
    "你以无头模式（非交互）为小元AI平台执行任务，用户通过云端聊天与你对话。"
    "复杂任务先用 TodoWrite 制定计划（分步骤），再逐步执行并更新完成状态。"
    "当用户要求记住信息（如「记住我喜欢…」）时，在回复末尾单独加一行，格式："
    "【记住】要记住的事实（每行一条，可多行）——系统会把它们写入用户的长期记忆。"
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


def _urlreq_request_json(base: str, agent_id: str, secret: str, body: dict):
    """带 Agent 鉴权头的 POST（返回 None 表示失败）"""
    import urllib.request as _urlreq

    try:
        req = _urlreq.Request(f"{base}/api/v1/agent/bridge-memory",
                              data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                              method="POST")
        req.add_header("X-Agent-Id", agent_id)
        req.add_header("X-Agent-Secret", secret)
        req.add_header("Content-Type", "application/json")
        with _urlreq.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


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

    def __init__(self, ws_send=None, server_url: str = "", agent_id: str = "",
                 agent_token: str = ""):
        self._ws_send = ws_send  # callable(event) fire-and-forget（心跳等旁路事件）
        self._server_url = server_url  # 记忆上传用（【记住】标记 → 云端 REST）
        self._sessions = SessionStore(SESSIONS_FILE)
        self._sessions.load()
        self._locks = {}  # cloud session_id -> asyncio.Lock（防并发 query）
        self._pending_approvals = {}  # decision_id -> asyncio.Future（SDK 审批流启用后使用）
        # 全局并发上限：Claude Code 子进程重量级（内存 + 网关配额），默认 2
        max_conc = int(os.getenv("CLAUDE_BRIDGE_MAX_CONCURRENCY", "2"))
        self._sem = asyncio.Semaphore(max_conc)

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
        if self._sem.locked():
            yield error_event("本机 Claude Code 正忙（并发任务已满），请稍后再试", rid)
            return
        async with self._sem:
            async with lock:
                async for ev in self._run_query(req, rid, prompt):
                    yield ev

    async def _run_query(self, req: ChatRequest, rid: str, prompt: str):
        claude_path = shutil.which(CLAUDE_CLI)
        if claude_path is None:
            yield error_event("本机未安装 Claude Code CLI（请先安装并登录 claude）", rid)
            return

        # fail-closed 门禁：安全钩子未就绪绝不 spawn 子进程（S0.1 C1 修复）
        ok, reason = guard_ready(str(PROJECT_ROOT))
        if not ok:
            logger.error("拒绝启动 Claude Code：%s", reason)
            yield error_event(f"安全钩子未就绪，已拒绝启动 Claude Code：{reason}", rid)
            return

        yield sender_event("claude", rid)

        resume_sid = self._sessions.get(req.session_id)
        claude_sid = resume_sid or str(uuid.uuid4())
        cmd = [
            claude_path, "-p", prompt,
            "--output-format", "stream-json", "--verbose",
            "--include-partial-messages",
            "--permission-mode", "acceptEdits",
            "--allowedTools", build_allowed_tools(),
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
                            yield ev_tool_start(name, rid, sender="claude")
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
                            yield ev_tool_end(name, output, rid, sender="claude")

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
            # 解析【记住】标记 → 云端写入用户长期记忆（失败静默，不阻塞回复）
            self._flush_memory_markers(req, final_result)
            yield ev_done(final_result, "", rid)

    def _flush_memory_markers(self, req: ChatRequest, text: str) -> None:
        """从回复中提取【记住】行，经云端端点写入用户长期记忆"""
        import re as _re
        import urllib.request as _urlreq

        facts = []
        for line in text.splitlines():
            m = _re.match(r"^【记住】(.*)$", line.strip())
            if m and m.group(1).strip():
                facts.append(m.group(1).strip())
        if not facts or not self._server_url:
            return
        try:
            base = self._server_url.replace("ws://", "http://").replace("wss://", "https://").rstrip("/")
            # 二合一进程走 tray：server_url/agent_id/token 从 main 传入；
            # 独立桥接进程：agent_token 即设备 secret
            from agent.main import load_identity
            identity = load_identity()
            agent_id = str(getattr(self, "_agent_id", "") or identity.get("agent_id") or "")
            secret = str(getattr(self, "_agent_token", "") or identity.get("agent_secret") or "")
            payload = _urlreq_request_json(base, agent_id, secret, {
                "user_id": int(getattr(req, "user_id", 0) or 0),
                "facts": facts[:20],
            })
            if payload:
                logger.info("记忆标记已写入: %d 条 (user=%s)", len(facts), getattr(req, "user_id", 0))
        except Exception:
            logger.warning("记忆标记写入失败（忽略）", exc_info=True)


def parse_args():
    p = argparse.ArgumentParser(description="小元AI Claude Code 桥接进程")
    p.add_argument("--server-url", default=None, help="云端 WebSocket 地址（默认 wss://cjyuanai.cn）")
    p.add_argument("--agent-id", default=None, help="Agent 唯一标识（机器模式：由安装注册自动获得）")
    p.add_argument("--agent-name", default="Claude Code 桥接", help="Agent 显示名称")
    p.add_argument("--agent-token", default=None,
                   help="Agent 认证凭据（默认：命令行 > 身份文件 > CLAUDE_BRIDGE_TOKEN/AGENT_TOKEN 环境变量）")
    args = p.parse_args()
    # 机器模式：未显式指定时回退到安装注册保存的身份，再回退环境变量
    from agent.main import load_identity
    identity = load_identity()
    if not args.agent_id:
        args.agent_id = str(identity.get("agent_id") or socket.gethostname())
    if not args.agent_token:
        args.agent_token = identity.get("agent_secret", "") or \
            os.getenv("CLAUDE_BRIDGE_TOKEN", "") or os.getenv("AGENT_TOKEN", "")
    if not args.server_url:
        args.server_url = identity.get("server_url") or "wss://cjyuanai.cn"
    # S3.3：强制 wss（ws:// 仅允许 localhost 开发 + env 显式豁免）
    from urllib.parse import urlparse as _urlparse
    _host = _urlparse(args.server_url).hostname or ""
    if args.server_url.startswith("ws://") and not (
            _host in ("localhost", "127.0.0.1") and os.getenv("AGENT_ALLOW_INSECURE_WS") == "1"):
        raise SystemExit(f"拒绝明文 ws:// 连接（{args.server_url}）："
                         "本地开发可设 AGENT_ALLOW_INSECURE_WS=1")
    return args


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

    handler = ClaudeBridgeHandler(server_url=args.server_url, agent_id=args.agent_id, agent_token=args.agent_token)
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
