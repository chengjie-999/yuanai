"""Agent WebSocket 客户端：连接云端 Hub，收发消息"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Callable, Awaitable

import websockets
from websockets import connect
from websockets.exceptions import ConnectionClosed

from yuanai_core.core.schemas import (
    ChatRequest, AgentEvent,
    token, reasoning, tool_start, tool_end, image_event, done, error_event,
    agent_hello, pong,
)

logger = logging.getLogger(__name__)

RECONNECT_MIN = 1
RECONNECT_MAX = 60


class AgentWSClient:
    """Agent 端 WebSocket 客户端"""

    def __init__(
        self,
        server_url: str,
        agent_id: str,
        agent_name: str,
        capabilities: list[str],
        agent_token: str = "",
        on_chat_request: Callable[[ChatRequest], AsyncGenerator[AgentEvent, None]] | None = None,
    ):
        self.server_url = server_url
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.capabilities = capabilities
        self.agent_token = agent_token
        self._on_chat_request = on_chat_request
        self._ws = None
        self._running = False
        self._status = "offline"  # offline | connecting | online | reconnecting
        self._pending_tasks: set[asyncio.Task] = set()

    def _track_task(self, coro) -> asyncio.Task:
        """创建已追踪的 Task，异常时自动记录日志"""
        task = asyncio.create_task(coro)
        self._pending_tasks.add(task)

        def _done(t: asyncio.Task):
            self._pending_tasks.discard(t)
            if not t.cancelled() and t.exception():
                logger.error("后台任务异常", exc_info=t.exception())
        task.add_done_callback(_done)
        return task

    def on_chat_request(
        self, handler: Callable[[ChatRequest], AsyncGenerator[AgentEvent, None]]
    ):
        """注册对话请求处理器"""
        self._on_chat_request = handler

    async def connect(self):
        """建立 WebSocket 连接并进入消息循环"""
        self._running = True
        backoff = RECONNECT_MIN

        while self._running:
            try:
                url = f"{self.server_url}/api/v1/agent/ws/agent/{self.agent_id}"
                if self.agent_token:
                    url += f"?token={self.agent_token}"
                self._status = "connecting"
                logger.info("正在连接云端: %s", url)
                self._ws = await connect(url, ping_interval=None)

                # 发送注册消息
                await self._ws.send(json.dumps({
                    "type": "hello",
                    "data": {
                        "agent_name": self.agent_name,
                        "capabilities": self.capabilities,
                    },
                }, ensure_ascii=False))
                self._status = "online"
                logger.info("已连接到云端，Agent: %s，能力: %s", self.agent_name, self.capabilities)
                backoff = RECONNECT_MIN

                # 消息循环
                async for raw in self._ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.warning("无法解析消息: %s", raw[:200])
                        continue

                    msg_type = msg.get("type", "")

                    if msg_type == "ping":
                        await self._ws.send(json.dumps({"type": "pong"}))
                        continue

                    if msg_type == "chat_request":
                        self._track_task(self._handle_chat_request(msg))
                    else:
                        logger.debug("未知消息类型: %s", msg_type)

            except (ConnectionClosed, OSError) as e:
                logger.warning("WebSocket 断开: %s", e)
            except Exception as e:
                logger.error("WebSocket 异常: %s", e, exc_info=True)
            finally:
                self._ws = None
                if self._running:
                    self._status = "reconnecting"
                    logger.info("将在 %ds 后重连...", backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, RECONNECT_MAX)

    async def _handle_chat_request(self, msg: dict):
        """处理云端发来的对话请求，将 Agent 事件逐个回传"""
        request_id = msg.get("request_id", "")
        logger.info("收到对话请求: %s", request_id)

        req = ChatRequest(
            request_id=request_id,
            session_id=msg.get("session_id", ""),
            messages=msg.get("messages", []),
            images=msg.get("images", []),
        )

        if not self._on_chat_request:
            await self._send(error_event("Agent 未配置对话处理器", request_id))
            return

        try:
            async for event in self._on_chat_request(req):
                await self._send(event)
        except Exception as e:
            logger.error("对话处理异常: %s", e, exc_info=True)
            await self._send(error_event(str(e), request_id))

    async def _send(self, event: AgentEvent):
        """发送事件到云端"""
        if self._ws:
            try:
                payload = json.dumps({
                    "type": event.type,
                    "data": event.data,
                    "request_id": event.request_id,
                }, ensure_ascii=False)
                await self._ws.send(payload)
            except Exception as e:
                logger.error("发送事件失败: %s", e)

    def send_activity(self, event: AgentEvent):
        """从同步上下文发送活动事件（fire-and-forget）"""
        try:
            loop = asyncio.get_running_loop()
            self._track_task(self._send(event))
        except RuntimeError:
            pass  # 不在事件循环中，忽略

    async def disconnect(self):
        """断开连接"""
        self._running = False
        for task in list(self._pending_tasks):
            task.cancel()
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
        if self._ws:
            await self._ws.close()
