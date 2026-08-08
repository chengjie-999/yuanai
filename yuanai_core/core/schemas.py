"""云边消息协议：云端↔Agent（WebSocket）和 云端↔前端（SSE）"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════
# WebSocket: 云端 → 本地 Agent
# ═══════════════════════════════════════════════════════════════

@dataclass
class ChatRequest:
    """云端转发给本地 Agent 的用户对话请求"""
    type: str = "chat_request"
    request_id: str = ""
    session_id: str = ""
    user_id: int = 0
    messages: List[Dict[str, Any]] = field(default_factory=list)
    images: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.request_id:
            self.request_id = str(uuid.uuid4())


@dataclass
class HeartbeatRequest:
    """云端心跳 ping"""
    type: str = "ping"


# ═══════════════════════════════════════════════════════════════
# WebSocket: 本地 Agent → 云端
# ═══════════════════════════════════════════════════════════════

@dataclass
class AgentEvent:
    """Agent 回传给云端的流式事件基类"""
    type: str
    data: Any
    request_id: str = ""


def token(text: str, request_id: str = "") -> AgentEvent:
    return AgentEvent(type="token", data=text, request_id=request_id)


def reasoning(text: str, request_id: str = "") -> AgentEvent:
    return AgentEvent(type="reasoning", data=text, request_id=request_id)


def tool_start(name: str, request_id: str = "") -> AgentEvent:
    return AgentEvent(type="tool_start", data={"name": name}, request_id=request_id)


def tool_end(name: str, output: str, request_id: str = "") -> AgentEvent:
    return AgentEvent(type="tool_end", data={"name": name, "output": output}, request_id=request_id)


def image_event(data_url: str, request_id: str = "") -> AgentEvent:
    return AgentEvent(type="image", data=data_url, request_id=request_id)


def done(display_content: str, reasoning_content: str = "", request_id: str = "") -> AgentEvent:
    return AgentEvent(
        type="done",
        data={"display_content": display_content, "reasoning_content": reasoning_content},
        request_id=request_id,
    )


def dashboard_event(session_id: str, request_id: str = "") -> AgentEvent:
    return AgentEvent(type="dashboard", data={"session_id": session_id}, request_id=request_id)


def html_event(url: str, request_id: str = "") -> AgentEvent:
    """交互式 HTML 图表（plotly 等），前端以 iframe 渲染"""
    return AgentEvent(type="html", data={"url": url}, request_id=request_id)


def error_event(message: str, request_id: str = "") -> AgentEvent:
    return AgentEvent(type="error", data=message, request_id=request_id)


def progress(current: int, total: int, message: str = "", request_id: str = "") -> AgentEvent:
    return AgentEvent(
        type="progress",
        data={"current": current, "total": total, "message": message},
        request_id=request_id,
    )


def activity_event(message: str, detail: str = "", request_id: str = "") -> AgentEvent:
    """Agent 当前活动状态（实时显示在管理面板）"""
    return AgentEvent(type="activity", data={"message": message, "detail": detail}, request_id=request_id)


def agent_hello(agent_name: str, capabilities: List[str]) -> AgentEvent:
    """Agent 首次连接时的注册消息"""
    return AgentEvent(
        type="hello",
        data={"agent_name": agent_name, "capabilities": capabilities},
    )


def pong() -> AgentEvent:
    return AgentEvent(type="pong", data="")


# ═══════════════════════════════════════════════════════════════
# SSE: 云端 → 前端（与现有格式兼容）
# ═══════════════════════════════════════════════════════════════

def sse_event(event: AgentEvent) -> Dict[str, Any]:
    """把 AgentEvent 转为 SSE 响应 dict"""
    return {"type": event.type, "data": event.data}
