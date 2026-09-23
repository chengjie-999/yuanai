# Claude Code 桥接 — 生产部署指南

桥接链路：用户本机 Claude Code（第三方网关模式）← `agent/claude_bridge.py` 进程 ← WebSocket → 云端 → 前端「⌘ Claude Code」模式。

## 一、云端一次性准备

1. 后台「用户管理」创建专属用户 `claude_bridge`（role=user）
2. 签发长令牌（≤365 天）：
   ```
   POST /api/v1/admin/agent-token   {"user_id": <该用户id>, "expires_days": 365}
   ```
3. 服务器 `.env` 增加：
   ```bash
   CLAUDE_BRIDGE_AGENT_ID=<该用户id>          # 桥接 WS 走此用户身份
   CLAUDE_BRIDGE_ALLOWED_USERNAMES=chengjie   # 白名单：只有这些用户名能用 ⌘ 模式（逗号分隔）
   ```
4. 重建后端容器（`docker compose up -d --build backend`）

## 二、用户本机启动桥接进程

```bash
python -m agent.claude_bridge --server-url wss://cjyuanai.cn --agent-id <用户id> --agent-token <长令牌>
```

- 验证：`python -m agent.verify_claude_bridge`（离线断言 agent→token→tool→done + 会话续接）
- 前端输入区「⌘ Claude Code」模式由在线状态轮询点亮（白名单用户可见）

## 三、待定项（用户决策后实施）

- [ ] 桥接进程常驻：托盘菜单加开关（tray.py 集成）/ Windows 计划任务开机自启
- [ ] 审批流：依赖 claude-agent-sdk（本地 pypi/清华源均无此包，官方 pypi 不通），
      装上后走 can_use_tool 审批流（前端 ApprovalCard 已就绪，事件协议已实现）
- [ ] nginx 对 `/api/v1/agent/ws/` 已关 access_log（25dbe53）

## 相关代码

- 桥接进程：`agent/claude_bridge.py`（CLI stream-json 引擎，SDK 不可用时的降级实现）
- 云端端点：`POST /api/v1/chat/claude-stream`（复用 SSE 桥；离线回退云端 LLM）
- 会话映射：`data/claude_sessions.json`（cloud session_id → claude session uuid）
- 事件：`sender_event` / `approval_event`（`yuanai_core/core/schemas.py`）
