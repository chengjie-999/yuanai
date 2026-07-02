# 小元AI — 云边协同多智能体平台

## 项目概览

前后端分离的多智能体协作平台，以对话为统一入口，集成数据分析、数据采集、浏览器自动化。Web 运行在云服务器（火山引擎），本地 Agent 负责实际任务执行。统筹 Agent（Orchestrator）自动识别意图并委派专业子 Agent 处理。

## 启动方式

```bash
# 云端 API（端口 8000）
python -m api.main

# React 前端（端口 5173）
cd frontend && npm run dev

# 本地 Agent（命令行模式，开发调试用）
python -m agent.main --agent-id 1

# 本地 Agent（托盘模式，发布用）
python -m agent.main --agent-id 1 --tray
```

## 多智能体架构

```
用户 → Web 对话界面 → SSE → FastAPI → WebSocket → 本地 Agent
                                                        │
                                              统筹 Agent（意图路由）
                                             ┌──────┼──────┐
                                        数据分析  数据采集  自动化
                                         Agent    Agent    Agent
```

**Agent 模型分配：**

| Agent | 模型 | 职责 |
|-------|------|------|
| 统筹 | doubao-seed-2-0-lite | 意图识别 + 任务路由 |
| 数据分析 | doubao-seed-2-0-pro | 数据集管理、统计、图表 |
| 数据采集 | doubao-seed-2-0-lite | 网页爬取、数据抓取 |
| 自动化 | doubao-seed-2-0-pro | 浏览器控制、题目审核、截图监控 |

## 目录结构

```
api/                    FastAPI 后端
├── main.py             应用入口（CORS、路由注册）
└── v1/
    ├── chat/router.py      SSE 对话 + Agent WebSocket 桥接
    ├── agent/router.py     WebSocket Hub（Agent 注册/心跳/中继）
    ├── admin/router.py     后台管理 API（仪表盘/用户/Agent状态/模型配置）
    ├── auth/               JWT 认证
    ├── data/               数据集管理
    ├── knowledge/           知识库
    ├── analysis/           分析大屏 API（RFM、dashboard 数据服务）
    └── ...
agent/                  本地 Agent 运行时 ★
├── main.py              入口（--tray 托盘 / 默认命令行）
├── orchestrator.py      统筹 Agent（3 个 delegate 工具）
├── ws_client.py         WebSocket 客户端（自动重连）
├── tray.py              系统托盘程序（pystray）
├── verify.py            多智能体链路验证脚本
├── yuanai_agent.spec    PyInstaller 打包规格
├── agents/              子 Agent
│   ├── analysis.py      数据分析子 Agent
│   ├── collection.py    数据采集子 Agent
│   └── automation.py    自动化子 Agent
├── tools/               Agent 专用工具（38 个）
│   ├── selenium_tools/  浏览器自动化
│   ├── audit_tools.py   审核知识库 + 反馈
│   └── ...
├── datanalysis/         数据分析脚本目录
│   ├── scripts/          独立分析脚本（Agent 自动发现）
│   │   ├── 描述性统计分析.py   统计 + 图表
│   │   ├── RFM客户分群.py     客户分群（内置示例数据）
│   │   ├── 客户流失预测.py     逻辑回归预测
│   │   └── bio_analysis.py    基因表达分析
│   └── crawl/             网页采集脚本
├── audit/               AI 审核系统（题目判定 + 结果解析）
└── rag.py               Milvus Lite 向量知识库
yuanai_core/            公共核心库（云边共用）
├── core/
│   ├── lc.py            LLM 工厂（DeepSeek / 豆包）
│   ├── chat.py          Agent 编排（DeepSeek V4 专用 + LangGraph 通用）
│   └── schemas.py       消息协议（WebSocket / SSE）
├── pure/                纯函数（无框架依赖）
└── tools/               通用工具（19 个，自动发现）
spiderlx/               浏览器自动化引擎（CDP/Selenium）
config/settings.py       模型 / JWT / 数据库配置
db/                      MySQL + Redis（云端）
frontend/                React 18 + TypeScript + React Router 前端
├── src/
│   ├── App.tsx               路由主入口（BrowserRouter + AuthProvider + 导航栏）
│   ├── contexts/
│   │   └── AuthContext.tsx   认证上下文
│   ├── pages/
│   │   ├── AgentAnalysisPage.tsx    数据分析全屏页（/agent/analysis）
│   │   ├── AgentAutomationPage.tsx  自动化全屏页（/agent/automation）
│   │   └── AgentKnowledgePage.tsx   知识库全屏页（/agent/knowledge）
│   └── components/
│       ├── ChatPage.tsx           对话界面（群聊式多 Agent 气泡）
│       ├── AdminPage.tsx          后台管理（11 Tab，嵌套路由 /admin/*）
│       ├── LoginPage.tsx          登录页（/login）
│       ├── AgentStatus.tsx        顶部栏 Agent 在线指示灯
│       ├── ToolCallCard.tsx       工具调用卡片（含 Agent 身份标签）
│       └── MarkdownContent.tsx    富文本渲染（表格/代码/图片）
data/                   数据目录
```

## 对话界面

唯一业务入口。欢迎页居中显示输入框，历史对话以群聊形式展示：
- 蓝色 = 小元AI（统筹）
- 紫色 = 数据分析 Agent
- 青色 = 数据采集 Agent
- 橙色 = 自动化 Agent

每个 Agent 气泡上方有彩色标签和身份标识，工具调用卡片显示 Agent 归属。

## 后台管理

11 个 Tab，每个有独立 URL 路由（`/admin/:tab`）：

| Tab | 路由 | 内容 |
|-----|------|------|
| 仪表盘 | `/admin/dashboard` | 用户数/会话数/消息数/在线Agent + 30天消息量图 |
| 用户管理 | `/admin/users` | 创建/冻结/删除用户 |
| 网站管理 | `/admin/websites` | 添加/删除采集网站 |
| Agent 状态 | `/admin/agents` | 在线状态 + 4 个子 Agent 团队卡片 + 实时活动记录 |
| 会话记录 | `/admin/sessions` | 历史会话查询 |
| 模型配置 | `/admin/models` | 已配置模型列表 |
| 数据集 | `/admin/datasets` | 上传/查看/删除数据集 |
| 知识库 | `/admin/knowledge` | 知识库文档管理 |
| 文件管理 | `/admin/files` | 服务器文件浏览 |
| 工具 | `/admin/tools` | 已注册工具列表 |
| 设置 | `/admin/settings` | 系统设置 |

## WebSocket 桥接

- 本地 Agent 主动连接云端 `ws://<server>/api/v1/agent/ws/agent/{agent_id}`
- 云端收到 HTTP 对话请求 → 检查 Agent 在线 → WebSocket 转发 → Agent 处理后回传 → SSE 推送前端
- Agent 离线时自动回退到云端直接调用 LLM

## 工具系统

- 通用工具：`yuanai_core/tools/__init__.py` 递归扫描，19 个
- Agent 专用工具：`agent/tools/__init__.py` 递归扫描 + 合并通用工具，共 57 个
- 工具自动发现：`isinstance(attr, BaseTool)` 判断，无需手动注册

## 权限

| 角色  | 聊天 | 后台管理 |
|-------|------|---------|
| admin | ✅   | ✅      |
| user  | ✅   | ❌      |

## 安全须知

- `.env` 已被 gitignore，永不提交
- API Key 从环境变量读取，不在源码硬编码
- URL 爬取有 SSRF 防护（内网地址拦截）
- JWT 鉴权中间件统一验证

## 数据分析大屏

分析 Agent 采用 ScriptDispatchAgent 模式：LLM 根据用户意图从 `agent/datanalysis/scripts/` 自动选择脚本，通过 subprocess 执行。

**脚本输出协议：**
- `__script_name__` / `__script_tags__` / `__script_params__` — 脚本元数据，ScriptRegistry 自动发现
- `__IMAGES__:path` — 图片输出（脚本 stdout），Registry 转为 base64 嵌入聊天
- `__RESULT__:{json}` — 结构化结果（用于大屏展示），Registry 检测后缓存到文件，通过 `__DASHBOARD__:path` 回传
- 协调器检测 `__DASHBOARD__` → 缓存至 Redis → 大屏页面读取渲染

**大屏页面：**
- `/agent/rfm` — RFM 3D 散点大屏（直连 API，不需要 Agent）
- `/agent/dashboard/:sessionId` — 通用分析大屏（从 Redis 读取 Agent 执行结果，降级到直连 API）
- 聊天中分析 Agent 消息的"打开面板"按钮指向 `/agent/dashboard/{sessionId}`

**分析 API：**
- `POST /api/v1/analysis/rfm` — RFM 分析（支持 dataset_id 或默认示例文件）
- `GET /api/v1/analysis/dashboard/{session_id}` — 读取 Agent 缓存的仪表盘数据
- `GET /api/v1/analysis/rfm-chart/{filename}` — Plotly 3D 图表 HTML（公开路径，iframe 嵌入）

**内置工具（Agent 可直接调用）：**
- `list_datasets` / `preview_dataset` / `analyze_dataset` — 数据集管理
- `transform_dataset` — 数据转换（筛选/分组聚合/透视表）
