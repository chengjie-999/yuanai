# 项目大方向定版：主对话入口 + CC 终端本地形态（2026-11-15 用户拍板「先完善愿景和大方向，不要偏」）

## 一句话方向

**网站/移动端 = 主对话入口（操控 + 监控本地智能体）；本地以终端形式运行——直接用 Claude Code 终端，并让它具备本地其他智能体的发现与调用能力、跨系统运行能力。**

## 分层形态

```
网站 / 移动端（主对话入口）── 操控：发指令、建计划、审批、委派
                             监控：执行观测、计划进度、CC 活动、产物回看
        │ SSE / WebSocket
        ▼
云端统筹 Orchestrator（意图路由 + function calling + 委派）
        │ 委派
        ▼
本地（终端形态 = Claude Code 终端 + 小元AI 本地 MCP）
   ├─ CC 终端（用户已装 claude）：对话/代码/终端/Git 原生能力
   │    ├─ 本地智能体发现与调用（MCP 工具面）
   │    └─ 跨系统运行：shell / 浏览器 / 文件 / 计划执行器 / 托盘 Agent
   ├─ 托盘 Agent：后台执行体（WS 云端连接、计划执行器、自动化、脚本）
   └─ yuan 终端：无凭证用户的本地终端（平台云端为模型层，保留维护）
```

## 三个入口的定位与关系

| 入口 | 角色 | 主投资方向 |
|------|------|-----------|
| **网站/移动端** | **主对话入口**：操控（发指令/建计划/审批/委派）+ 监控（执行观测/计划进度/CC 活动/产物回看） | ✅ 核心 |
| **CC 终端（本地主形态）** | 有模型凭证用户的本机第一入口：直接用 claude，经「小元AI 本地 MCP」发现并调用本地智能体，跨系统执行；凭证=用户自持（DeepSeek 官方集成指南），平台不代付（Anthropic 2026-09 条款） | ✅ 核心（新） |
| **yuan 终端** | **无凭证用户的本地终端**（平台云端为模型层，可访问云端会话）——**不是「网站桌面客户端」**（与主入口定位相悖，2026-11-15 用户拍板修正） | 保留维护，普通用户本地主路径 |
| 托盘 Agent / 桌宠 | 后台执行体 + 状态可视化 | 维持 |

## CC 终端增强路线（本地形态核心，新立项）

### A. 小元AI 本地 MCP 服务器（发现 + 调用）
- `agent/mcp_server.py`：把本地智能体能力暴露为 MCP 工具（Python mcp SDK 或轻量 stdio JSON-RPC 实现）
- 工具面（对齐「发现和调用」）：
  - **发现**：`list_local_agents`（统筹/自动化/脚本 registry 清单/计划队列/桌宠状态/托盘在线态）
  - **调用**：`script_*`（9 个分析脚本 + 采集）、`run_automation`（浏览器自动化 react Agent）、`create_plan`/`execute_plan`/`plan_status`（计划闭环）、`remember`/`get_memory`（记忆）、`retrieve_planet_knowledge`（知识星球）、`cloud_chat`（桥接云端统筹/同步网站会话）
- 用户侧：安装指引直接链接 DeepSeek 官方集成指南（用户自持 key 合规路径）；MCP 注册一行 `claude mcp add`

### B. 跨系统运行
- CC 原生：shell / 文件 / Git（已有）
- MCP 桥接：浏览器自动化（spiderlx）、脚本执行（ScriptRegistry）、计划执行器（云端队列）、托盘 Agent 状态/开关
- 本机各子系统统一由 CC 终端一个入口调度

### C. 与现有资产的关系（不推翻）
- CC 桥接（网站 → 本机 CC 执行通道）不变——网站主入口委派到本机 CC 的既有链路
- 自研 yuan 终端保留（无凭证用户的本地终端），其窗口接续/15s 增量同步等能力继续维护
- 桌宠六态联动不变；yuancc 薄封装保留

## 路线（建议执行序）

1. **A1 本地 MCP 最小面**：stdio MCP 服务器 + 发现工具（list_local_agents）+ script_* 调用透传 ScriptRegistry——CC 终端即可发现并调用分析脚本（最快见效）
2. **A2 调用面扩展**：automation / 计划 / 记忆 / 知识星球 / cloud_chat
3. **A3 注册与分发**：CC 安装指引直接链接 DeepSeek 官方集成指南（https://api-docs.deepseek.com/zh-cn/quick_start/agent_integrations/claude_code，用户自持凭证，平台零代付——Anthropic 2026-09 条款禁代付/中介流量）+ MCP 一行注册；不自建 CC 安装分发
4. 挂账：CC 浏览器 MCP（并入 A2）、MCP 客户端反方向（本地 Agent 消费 dsh 生态，product-positioning 路径 A 保留）

## 与既有文档的关系

- 本文件 = 大方向定版，优先级最高；`plans/terminal-vision-2026-11.md` 的 P0-P2（自研终端增强）降为「yuan 终端维护线」，已落地部分全部保留
- `plans/todo-2026-11.md` 看板同步更新（CC 终端 MCP 列为核心新项）
- CLAUDE.md 项目概览/智能体架构图按本文件更新

## 决策点（待拍板）

| # | 决策 | 建议 |
|---|------|------|
| V1 | MCP 实现形态 | Python 官方 mcp SDK（企业级，与「借 MCP 生态」策略一致）vs 轻量 stdio 实现（零依赖）；建议先用 mcp SDK |
| V2 | 注册方式 | **已拍板（2026-11-15）**：CC 安装直接链接 DeepSeek 官方集成指南；MCP 注册一行 `claude mcp add` |
| V3 | yuan 终端投入 | 维持现状不再扩功能（已建能力保留）；品牌对齐 T2 等挂账继续排队 |
