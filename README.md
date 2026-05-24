# 小元AI — 云边协同多智能体平台

[![Python](https://img.shields.io/badge/Python-3.10-blue)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-61dafb)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688)](https://fastapi.tiangolo.com/)

前后端分离的多智能体协作平台，以对话为统一入口，集成数据分析、数据采集、浏览器自动化。云服务器（火山引擎）运行 Web 服务，本地 Agent 负责实际任务执行。统筹 Agent 自动识别意图并委派专业子 Agent 处理。

---

## 快速开始

### 环境

- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- Redis（可选，用于聊天缓存）

### 安装

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### 初始化数据库

```sql
CREATE DATABASE ai_agent DEFAULT CHARSET utf8mb4;
```

### 启动

**云后端 API（端口 8000）**：
```bash
python -m api.main
```

**React 前端（端口 5173）**：
```bash
cd frontend && npm run dev
```

**本地 Agent（命令行模式，开发调试用）**：
```bash
python -m agent.main --agent-id 1
```

**本地 Agent（系统托盘模式，发布用）**：
```bash
python -m agent.main --agent-id 1 --tray
```

### 创建管理员

启动后用 admin 账号登录后台管理页 → 用户管理 → **创建用户**，设置角色为 admin。

---

## 多智能体架构

```
用户 → Web 对话界面 → SSE → FastAPI → WebSocket → 本地 Agent
                                                        │
                                              统筹 Agent（意图路由）
                                             ┌──────┼──────┐
                                        数据分析  数据采集  自动化
                                         Agent    Agent    Agent
```

| Agent | 模型 | 职责 |
|-------|------|------|
| 统筹 | doubao-seed-2-0-lite | 意图识别 + 任务路由 |
| 数据分析 | doubao-seed-2-0-pro | 数据集管理、统计、图表 |
| 数据采集 | doubao-seed-2-0-lite | 网页爬取、数据抓取 |
| 自动化 | doubao-seed-2-0-pro | 浏览器控制、题目审核、截图监控 |

### 对话界面

唯一业务入口，以群聊形式展示多 Agent 协作：

| 颜色 | 身份 |
|------|------|
| 蓝色 | 小元AI（统筹） |
| 紫色 | 数据分析 Agent |
| 青色 | 数据采集 Agent |
| 橙色 | 自动化 Agent |

每个 Agent 气泡上方有彩色标签和身份标识，工具调用卡片显示 Agent 归属。

### WebSocket 桥接

- 本地 Agent 主动连接云端 `ws://<server>/api/v1/agent/ws/agent/{agent_id}`
- HTTP 对话请求 → 检查 Agent 在线 → WebSocket 转发 → Agent 处理后回传 → SSE 推送前端
- Agent 离线时自动回退到云端直接调用 LLM

---

## 功能模块

### 后台管理（仅 admin）

7 个 Tab：

| Tab | 内容 |
|-----|------|
| 仪表盘 | 用户数/会话数/消息数/在线Agent + 30天消息量图 |
| 用户管理 | 创建/冻结/删除用户 |
| 网站管理 | 添加/删除采集网站 |
| Agent 状态 | 在线状态 + 4 个子 Agent 团队卡片 + 实时活动记录 |
| 模型配置 | 已配置模型列表 |

### 工具系统

- 通用工具：`yuanai_core/tools/` 递归扫描，19 个
- Agent 专用工具：`agent/tools/` 递归扫描 + 合并通用工具，共 57 个
- 工具自动发现：`isinstance(attr, BaseTool)` 判断，无需手动注册

---

## 权限系统

| 角色  | 聊天 | 后台管理 |
|-------|------|---------|
| admin | ✅   | ✅      |
| user  | ✅   | ❌      |

- JWT Token 存储在 localStorage，有效期 7 天
- 注册功能已关闭，仅 admin 可创建用户
- 用户可被冻结，冻结期间无法使用

### 公开路径

```
/                      健康检查
/health                健康检查
/api/v1/qimg/*         静态文件
/api/v1/chat/image/*   聊天图片
/api/v1/auth/login     登录
/api/v1/auth/check     Token 验证
/api/v1/auth/register  注册（返回关闭提示）
```

---

## API 概览

### 鉴权
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册（已关闭） |
| POST | `/api/v1/auth/login` | 登录 |
| POST | `/api/v1/auth/check` | 验证 Token |

### 聊天
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/chat/stream` | SSE 流式聊天 |
| POST | `/api/v1/chat/session/new` | 创建会话 |
| GET | `/api/v1/chat/sessions` | 会话列表 |
| DELETE | `/api/v1/chat/session/{id}` | 删除会话 |
| POST | `/api/v1/chat/messages` | 获取消息 |
| POST | `/api/v1/chat/save` | 保存消息 |
| GET | `/api/v1/chat/image/{sid}/{file}` | 聊天图片 |

### 数据管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/data/upload` | 上传数据集 |
| GET | `/api/v1/data/datasets` | 数据集列表 |
| GET | `/api/v1/data/dataset/{id}` | 数据集详情 |
| GET | `/api/v1/data/analyze/{id}` | 分析数据集 |
| GET | `/api/v1/data/analysis-image/{id}/{name}` | 图表图片 |
| DELETE | `/api/v1/data/dataset/{id}` | 删除数据集 |

### Agent WebSocket
| 方法 | 路径 | 说明 |
|------|------|------|
| WS | `/api/v1/agent/ws/agent/{id}` | Agent 注册/心跳/中继 |
| GET | `/api/v1/agent/status` | Agent 在线状态 |

### 后台管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/users` | 用户列表 |
| POST | `/api/v1/admin/users/freeze` | 冻结/解冻 |
| POST | `/api/v1/admin/users/create` | 创建用户 |
| DELETE | `/api/v1/admin/users/{id}` | 删除用户 |
| GET | `/api/v1/admin/websites` | 网站列表 |
| POST | `/api/v1/admin/websites` | 添加网站 |
| DELETE | `/api/v1/admin/websites/{id}` | 删除网站 |

---

## 目录结构

```
api/                    FastAPI 后端
├── main.py             应用入口（CORS、路由注册）
└── v1/
    ├── chat/router.py      SSE 对话 + Agent WebSocket 桥接
    ├── agent/router.py     WebSocket Hub（Agent 注册/心跳/中继）
    ├── admin/router.py     后台管理 API
    ├── auth/               JWT 认证
    ├── data/               数据集管理
    ├── knowledge/           知识库
    └── ...

agent/                  本地 Agent 运行时
├── main.py              入口（--tray 托盘 / 默认命令行）
├── orchestrator.py      统筹 Agent（3 个 delegate 工具）
├── ws_client.py         WebSocket 客户端（自动重连）
├── tray.py              系统托盘程序（pystray）
├── agents/              子 Agent
│   ├── analysis.py      数据分析子 Agent
│   ├── collection.py    数据采集子 Agent
│   └── automation.py    自动化子 Agent
├── tools/               Agent 专用工具（38 个）
│   ├── selenium_tools/  浏览器自动化
│   └── audit_tools.py   审核知识库 + 反馈
└── audit/               AI 审核系统

yuanai_core/            公共核心库（云边共用）
├── core/
│   ├── lc.py            LLM 工厂（DeepSeek / 豆包）
│   ├── chat.py          Agent 编排
│   └── schemas.py       消息协议（WebSocket / SSE）
├── pure/                纯函数（无框架依赖）
└── tools/               通用工具（19 个，自动发现）

spiderlx/               浏览器自动化引擎（CDP/Selenium）

frontend/               React 18 + TypeScript 前端
├── src/
│   ├── App.tsx          主入口（对话 + 后台管理）
│   └── components/
│       ├── ChatPage.tsx      对话界面（群聊式多 Agent 气泡）
│       ├── AdminPage.tsx     后台管理
│       ├── AgentStatus.tsx   顶部栏 Agent 在线指示灯
│       ├── ToolCallCard.tsx  工具调用卡片（含 Agent 身份标签）
│       └── MarkdownContent.tsx  富文本渲染

config/settings.py      模型 / JWT / 数据库配置
db/                     MySQL + Redis（云端）
data/                   数据目录（聊天图片、爬取文件等）
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python, FastAPI, Uvicorn, LangChain, LangGraph, SQLAlchemy |
| 前端 | React 18, TypeScript, Vite |
| 数据库 | MySQL 8.0, Redis |
| 爬虫 | requests, BeautifulSoup, Selenium |
| AI | DeepSeek API, 豆包 API |
| 鉴权 | python-jose (JWT), bcrypt |
| 本地 Agent | WebSocket, pystray, PyInstaller |
| 配置 | `config/settings.py` 统一管理 |
| 业务层 | `yuanai_core/pure/` 纯 Python，无框架依赖 |
