# -*- coding: utf-8 -*-
"""终端云端对话通道（TUI v3.1 #37，2026-11-12）：终端 = 网站对话的桌面客户端
（第三端）——设备凭据换会话 JWT（POST /agent/chat-token，#40）→ 复用 /chat/*
用户端点（主对话/会话列表/历史/SSE 流/保存），与网页/手机看到同一批会话。

文案纪律（方案 terminal-tui-2026-11.md）：云端是小元AI 正身，一律不用
「兜底/离线应答」等词；云端对话失败时说「云端不可用」。
"""

import json
import logging

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "deepseek-flash"  # 与云端 ChatRequest 默认一致（主模型永远 deepseek）


def _https_url(server_url: str) -> str:
    """wss://cjyuanai.cn → https://cjyuanai.cn；ws://localhost:8000 → http://localhost:8000"""
    return (server_url or "").replace("wss://", "https://").replace("ws://", "http://").rstrip("/")


def _detail(resp) -> str:
    try:
        d = resp.json()
        if isinstance(d, dict):
            return str(d.get("detail", d))
        return str(d)[:200]
    except Exception:
        return (resp.text or "")[:200]


class CloudChatClient:
    """云端对话客户端：JWT 懒取（失效重取一次）+ 会话/消息/SSE 流/保存。"""

    def __init__(self, server_url: str, agent_id: str, agent_secret: str,
                 timeout: float = 30.0):
        import httpx
        self._base = _https_url(server_url)
        self._agent_id = str(agent_id)
        self._secret = agent_secret or ""
        self._timeout = timeout
        self._httpx = httpx
        self._token = ""       # 用户会话 JWT（懒取）
        self._display_name = ""

    # ———— 令牌（#40） ————

    def ensure_token(self) -> str:
        """设备凭据 → 绑定用户会话 JWT。失败抛 RuntimeError（人话）。"""
        if self._token:
            return self._token
        try:
            resp = self._httpx.post(
                f"{self._base}/api/v1/agent/chat-token",
                headers={"X-Agent-Id": self._agent_id,
                         "X-Agent-Secret": self._secret},
                timeout=self._timeout)
        except self._httpx.HTTPError as e:
            raise RuntimeError(f"无法连接云端（{self._base}）：{str(e)[:100]}")
        if resp.status_code == 200:
            d = resp.json()
            self._token = d.get("token", "")
            self._display_name = d.get("display_name", "") or d.get("username", "")
            if not self._token:
                raise RuntimeError("云端未返回令牌（响应异常）")
            return self._token
        if resp.status_code == 403:
            raise RuntimeError(f"本机 Agent 未绑定账号或账号受限：{_detail(resp)}"
                               "——请先在网页登录并完成设备绑定")
        raise RuntimeError(f"换取会话令牌失败（HTTP {resp.status_code}）：{_detail(resp)}")

    def invalidate_token(self) -> None:
        self._token = ""

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.ensure_token()}"}

    # ———— 会话/消息 ————

    def main_session_id(self) -> str:
        """确保/获取主对话（豆包式置顶主对话，登录直接落主对话）"""
        resp = self._httpx.post(f"{self._base}/api/v1/chat/main-session",
                                headers=self._auth(), timeout=self._timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"获取主对话失败（HTTP {resp.status_code}）：{_detail(resp)}")
        return str(resp.json().get("session_id", ""))

    def list_sessions(self, agent_kind: str = "chat") -> list:
        """会话列表（2026-11-13 多窗口 v2 默认对话窗口；2026-11-15 本地终端
        访问云端会话：kind=claude 列 CC 窗口会话——「cc 是续接会话的终端指令」）"""
        resp = self._httpx.get(f"{self._base}/api/v1/chat/sessions",
                               params={"own": 1, "agent_kind": agent_kind}, headers=self._auth(),
                               timeout=self._timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"获取会话列表失败（HTTP {resp.status_code}）：{_detail(resp)}")
        return resp.json()

    def create_session(self, agent_kind: str) -> str:
        """新建窗口会话（迁移 0031 agent_kind：chat/claude/automation）"""
        resp = self._httpx.post(f"{self._base}/api/v1/chat/session/new",
                                json={"agent_kind": agent_kind},
                                headers=self._auth(), timeout=self._timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"新建会话失败（HTTP {resp.status_code}）：{_detail(resp)}")
        return str(resp.json().get("session_id", ""))

    def load_messages(self, session_id: str) -> list:
        resp = self._httpx.post(f"{self._base}/api/v1/chat/messages",
                                json={"session_id": session_id},
                                headers=self._auth(), timeout=self._timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"读取会话历史失败（HTTP {resp.status_code}）：{_detail(resp)}")
        return resp.json()

    def save_messages(self, session_id: str, messages: list) -> None:
        """全量保存（与网页 /chat/save 同链路——终端发的消息网站立即可见，多端互通）"""
        resp = self._httpx.post(f"{self._base}/api/v1/chat/save",
                                json={"session_id": session_id, "messages": messages},
                                headers=self._auth(), timeout=self._timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"保存对话失败（HTTP {resp.status_code}）：{_detail(resp)}")

    # ———— SSE 流（async 生成器：逐事件吐出，调用方按需 await 审批等交互） ————

    async def stream(self, session_id: str, prompt: str, history: list,
                     backend: str = "auto", kind: str = "chat"):
        """SSE 流 → 逐事件 yield dict。kind=chat → POST /chat/stream（小元窗口）；
        kind=claude → POST /chat/claude-stream（CC 窗口，云端桥接本机 CC——
        与网站 CC 窗口同链路，本地终端第三端）。401 时清令牌重试一次；
        非 200 抛 RuntimeError（人话）。事件类型与网页同口径：token /
        tool_start / tool_end / done / error / agent / mode_event / backend_event /
        usage_event / compliance_warning / approval / suggestions。"""
        endpoint = ("/api/v1/chat/claude-stream" if kind == "claude"
                    else "/api/v1/chat/stream")
        body = {"model": DEFAULT_MODEL, "prompt": prompt, "history": history,
                "session_id": session_id, "chat_backend": backend,
                "reasoning_effort": "low"}
        headers = {**self._auth(), "Accept": "text/event-stream"}
        timeout = self._httpx.Timeout(self._timeout, read=300.0)
        async with self._httpx.AsyncClient(timeout=timeout) as client:
            for attempt in (1, 2):
                try:
                    async with client.stream(
                            "POST", f"{self._base}{endpoint}",
                            json=body, headers=headers) as resp:
                        if resp.status_code == 401 and attempt == 1:
                            self.invalidate_token()
                            headers = {**self._auth(), "Accept": "text/event-stream"}
                            continue  # 令牌过期：重取重试一次
                        if resp.status_code != 200:
                            raise RuntimeError(
                                f"云端对话失败（HTTP {resp.status_code}）：{_detail(resp)}")
                        async for line in resp.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            payload = line[len("data:"):].strip()
                            if not payload:
                                continue
                            try:
                                ev = json.loads(payload)
                            except ValueError:
                                continue
                            if isinstance(ev, dict) and ev.get("type"):
                                yield ev
                    return
                except self._httpx.HTTPError as e:
                    raise RuntimeError(f"云端连接中断：{str(e)[:120]}")

    def send_decision(self, decision_id: str, approve: bool, kind: str = "chat") -> None:
        """V1-2 审批决议：POST body.decision 早分支配对（不烧配额不审核；
        kind=claude 走 claude-stream 端点——CC 窗口同款决议通道）"""
        endpoint = ("/api/v1/chat/claude-stream" if kind == "claude"
                    else "/api/v1/chat/stream")
        resp = self._httpx.post(
            f"{self._base}{endpoint}",
            json={"decision": {"decision_id": decision_id, "approve": approve}},
            headers=self._auth(), timeout=self._timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"审批决议发送失败（HTTP {resp.status_code}）")

    # ———— 观测/计划（v3.2 #38：终端观测右栏 + /plan 队列视图） ————

    def activity(self) -> dict:
        """执行观测面数据：/chat/cc-activity（用户 JWT 口径，本用户绑定设备/共享
        桥接的最近活动 + 在线状态）。返回 {online, latest, age_s, activities}"""
        resp = self._httpx.get(f"{self._base}/api/v1/chat/cc-activity",
                               headers=self._auth(), timeout=self._timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"观测数据获取失败（HTTP {resp.status_code}）：{_detail(resp)}")
        return resp.json() or {}

    def list_plans(self) -> list:
        """计划队列（与网站 /chat/plan 同列表：用户 JWT 口径，多端同一批计划）"""
        resp = self._httpx.get(f"{self._base}/api/v1/plan/list",
                               headers=self._auth(), timeout=self._timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"计划列表获取失败（HTTP {resp.status_code}）：{_detail(resp)}")
        return (resp.json() or {}).get("plans", [])

    def plan_detail(self, plan_id) -> dict:
        """单计划详情（plan + steps 步骤进度 + runs）"""
        resp = self._httpx.get(f"{self._base}/api/v1/plan/{plan_id}",
                               headers=self._auth(), timeout=self._timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"计划详情获取失败（HTTP {resp.status_code}）：{_detail(resp)}")
        return resp.json() or {}
