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

| Agent | 模型 | 架构 | 工具数 | 职责 |
|-------|------|------|:------:|------|
| 统筹 | doubao-seed-2-0-lite | Two-tier ReAct + 意图分类器 | 8-42（动态） | 意图识别 → 直接工具 / 委派子 Agent |
| 数据分析 | doubao-seed-2-0-pro | ScriptDispatch | 7 builtin + 9 脚本 | 数据集管理、统计分析、图表生成 |
| 数据采集 | doubao-seed-2-0-lite | ScriptDispatch | 8 builtin + 1 脚本 | 网页爬取、数据抓取、内容解析 |
| 自动化 | doubao-seed-2-0-pro | ReAct + 意图过滤 | 14-41（动态） | 浏览器控制、题目审核、截图监控 |

### Skill 系统（配置驱动，可扩展）

子 Agent 的能力定义从代码中解耦，统一在 `skills/` 目录下通过 YAML 配置：

```
skills/
├── __init__.py              SkillRegistry 注册中心（自动扫描子目录）
├── analysis/skill.yaml      数据分析：提示词、模型、脚本目录、内置工具
├── collection/skill.yaml    数据采集：提示词、模型、脚本目录、内置工具
└── automation/skill.yaml    自动化：提示词、模型、工具列表
```

- Orchestrator 遍历 `skill_registry.get_all()` 动态生成 `delegate_to_*_agent` 工具
- `agent/main.py` 的 capabilities 从 `skill_registry.names` 自动生成
- **加新能力**：新建 `skills/xxx/skill.yaml` + 可选脚本 → 重启 Agent → 自动注册（零代码改动）

### 对话界面

唯一业务入口，以群聊形式展示多 Agent 协作：

| 颜色 | 身份 |
|------|------|
| 蓝色 | 小元AI（统筹） |
| 紫色 | 数据分析 Agent |
| 青色 | 数据采集 Agent |
| 橙色 | 自动化 Agent |

每个 Agent 气泡上方有彩色标签和身份标识，工具调用卡片显示 Agent 归属。

当统筹委派子 Agent 时，消息中会出现 **打开面板 →** 按钮，点击在新标签页打开该 Agent 的**独立全屏操作页面**（`/chat/agent/analysis`、`/chat/agent/automation`、`/chat/agent/knowledge`），提供完整的数据分析、浏览器自动化、知识库检索功能。

### 前端路由

基于 React Router v6，支持独立页面链接和浏览器前进/后退：

| 路由 | 页面 | 权限 |
|------|------|------|
| `/` | 官网公开首页（免登录，聊天入口） | 公开 |
| `/login` | 登录/注册 | 公开 |
| `/chat` | 对话主页 | 需登录 |
| `/chat/user` | 个人信息 | 需登录 |
| `/chat/agent` | Agent 状态 | 需登录 |
| `/chat/agent/analysis` | 数据分析全屏面板 | 需登录 |
| `/chat/agent/automation` | 自动化全屏面板 | 需登录 |
| `/chat/agent/knowledge` | 知识库检索面板 | 需登录 |
| `/chat/admin/dashboard` | 仪表盘 | admin |
| `/chat/admin/users` | 用户管理 | admin |
| `/chat/admin/agents` | Agent 状态 | admin |
| `/chat/admin/sessions` | 会话记录 | admin |
| `/chat/admin/models` | 模型配置 | admin |
| `/chat/admin/*` | …其他 6 个管理 Tab | admin |

### WebSocket 桥接

- 本地 Agent 主动连接云端 `ws://<server>/api/v1/agent/ws/agent/{agent_id}`
- HTTP 对话请求 → 检查 Agent 在线 → WebSocket 转发 → Agent 处理后回传 → SSE 推送前端
- Agent 离线时自动回退到云端直接调用 LLM

---

## 功能模块

### 后台管理（仅 admin，嵌套路由 `/chat/admin/*`）

12 个 Tab，每个有独立 URL：

| Tab | 路由 | 内容 |
|-----|------|------|
| 仪表盘 | `/chat/admin/dashboard` | 用户数/会话数/消息数/在线Agent + 30天消息量图 |
| 用户管理 | `/chat/admin/users` | 创建/冻结/删除用户 |
| Agent 状态 | `/chat/admin/agents` | 在线状态 + 4 个子 Agent 团队卡片 + 实时活动记录 |
| 会话记录 | `/chat/admin/sessions` | 历史会话查询与查看 |
| 模型配置 | `/chat/admin/models` | 已配置模型列表 |
| 网站管理 | `/chat/admin/websites` | 添加/删除采集网站 |
| 数据集 | `/chat/admin/datasets` | 上传/查看/删除数据集 |
| 知识库 | `/chat/admin/knowledge` | 知识库文档管理 |
| 文件管理 | `/chat/admin/files` | 服务器文件浏览 |
| 工具 | `/chat/admin/tools` | 已注册工具列表 |
| 代码监控 | `/chat/admin/monitor` | Git 轮询 + 代码变更趋势图 + 文件类型分布 + 实时活动日志 |
| 设置 | `/chat/admin/settings` | 系统设置 |

### 工具系统

- 通用工具：`yuanai_core/tools/` 自动发现，**39 个**（8 模块，7 类别：general/crawl/data/file/memory/knowledge/stats）
- Agent 专用工具：`agent/tools/` 自动发现，**38 个**（浏览器/审核/Cookie/截图）
- **总计 80 个注册工具**，按 Agent 角色精准分配
- 工具类别标签 `TOOL_CATEGORY`：`load_tools_for("crawl", "data")` 按需加载
- 意图分类器：`agent/intent_classifier.py` — 关键词匹配 + LLM 降级，自动按意图加载工具子集，节省 30-55% token
- 直接命令（如 "200+300"）绕过 LLM 直接执行，**100% token 节省**

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
/api/v1/chat/image/*   聊天图片（immutable 缓存，前端不拼 token，跨登录命中缓存）
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
| POST | `/api/v1/chat/claude-stream` | Claude Code 桥接对话（admin/白名单；桥离线回退云端） |
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

### 数据分析
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/analysis/rfm` | RFM 客户分群分析 |
| GET | `/api/v1/analysis/dashboard/{id}` | 分析仪表盘数据 |
| GET | `/api/v1/analysis/rfm-chart/{file}` | 3D 散点图 HTML |

### Agent WebSocket
| 方法 | 路径 | 说明 |
|------|------|------|
| WS | `/api/v1/agent/ws/agent/{id}` | Agent 注册/心跳/中继 |
| GET | `/api/v1/agent/status` | Agent 在线状态 |

### 代码监控
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/monitor/status` | 会话汇总（文件数/行数/速度） |
| GET | `/api/v1/monitor/changes` | 最近文件变更列表 |
| GET | `/api/v1/monitor/timeline` | 时间序列累积数据 |
| GET | `/api/v1/monitor/file-types` | 文件类型分布 |
| GET | `/api/v1/monitor/top-files` | 最常变更文件排行 |

### 后台管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/users` | 用户列表 |
| POST | `/api/v1/admin/users/freeze` | 冻结/解冻 |
| POST | `/api/v1/admin/users/create` | 创建用户 |
| POST | `/api/v1/admin/agent-token` | 为本地 Agent 签发长生命周期 JWT（1-365 天，默认 180） |
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
    ├── monitor/           代码进度实时监控
    └── ...

agent/                  本地 Agent 运行时
├── main.py              入口（--tray 托盘 / 默认命令行）
├── orchestrator.py      统筹 Agent（动态 delegate 工具，从 skills/ 自动发现）
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
skills/                  Skill 配置中心（YAML 驱动，Agent 能力自动发现）

frontend/               React 18 + TypeScript + React Router 前端
├── src/
│   ├── App.tsx               路由主入口（BrowserRouter + AuthProvider；/ 公开首页，/chat/* 登录后应用）
│   ├── contexts/
│   │   └── AuthContext.tsx   认证上下文（token/user/login/logout）
│   ├── pages/
│   │   ├── AgentAnalysisPage.tsx    数据分析全屏页
│   │   ├── AgentAutomationPage.tsx  自动化全屏页
│   │   └── AgentKnowledgePage.tsx   知识库全屏页
│   └── components/
│       ├── ChatPage.tsx           对话界面（群聊式多 Agent 气泡）
│       ├── LandingPage.tsx        官网公开首页（免登录，聊天/后台入口）
│       ├── AdminPage.tsx          后台管理（11 Tab，嵌套路由）
│       ├── LoginPage.tsx          登录页
│       ├── AgentStatus.tsx        顶部栏 Agent 在线指示灯
│       ├── ToolCallCard.tsx       工具调用卡片（含 Agent 身份标签）
│       └── MarkdownContent.tsx    富文本渲染（表格/代码/图片）

config/settings.py      模型 / JWT / 数据库配置
db/                     MySQL + Redis（云端）
data/                   数据目录（聊天图片、爬取文件等）
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python, FastAPI, Uvicorn, LangChain, LangGraph, SQLAlchemy |
| 前端 | React 18, TypeScript, Vite, Recharts |
| 数据库 | MySQL 8.0, Redis, Milvus |
| 迁移 | Alembic（增量迁移，替代原始 ALTER TABLE） |
| 爬虫 | requests, BeautifulSoup, Selenium |
| AI | DeepSeek API, 豆包 API |
| 鉴权 | python-jose (JWT), bcrypt |
| 限流 | Redis + 内存降级（`api/v1/ratelimit.py`） |
| 本地 Agent | WebSocket, pystray, PyInstaller |
| CI/CD | GitHub Actions（test + lint + build + Docker） |
| 部署 | Docker Compose（MySQL + Redis + Milvus + 后端 + Nginx 前端） |
| 配置 | `config/settings.py` 统一管理 |
| 业务层 | `yuanai_core/pure/` 纯 Python，无框架依赖 |

---

## 测试

```bash
# 无需数据库的单元测试
pytest test/test_ratelimit.py test/test_auth.py test/test_db.py -v

# 全部测试（需完整 API 环境）
pytest test/ -v
```

## Claude Code 桥接（云端 ↔ 本机 Claude Code）

1. 后台「Agent 管理」签发安装码
2. 本机安装（需安装并登录 Claude Code CLI）：

```bash
python -m agent.main --install YUAN-XXXX-XXXX-XXXX   # 注册本机，保存 data/agent_identity.json
python -m agent.main                                  # 启动（统筹 + Claude 二合一进程）
```

3. 后台「Agent 管理」把该设备一对一绑定到用户账号
4. 前端聊天输入区切换到「⌘ Claude Code」模式后，消息直发本机 Claude Code（流式回复 + 工具卡片 + 会话续接）

安全边界：工具白名单 + `acceptEdits` + cwd 锁仓库 + 提示词黑名单 + 审计日志 `data/logs/claude_audit.log`。验证：`python -m agent.verify_claude_bridge`。

> 共享桥接模式（多用户共用一台本机）仍可用：云端设 `CLAUDE_BRIDGE_AGENT_ID` 指向专属设备，单独跑 `python -m agent.claude_bridge`。

## Docker 部署

```bash
cp .env.example .env  # 编辑生产环境变量
docker-compose up -d   # 启动 MySQL + Redis + Milvus + 后端 + 前端(nginx:80)
```

Nginx 配置（`deploy/nginx.conf`）已包含：WebSocket 升级支持、SSL 443 模板（备案后启用）、安全响应头、分级限流。备案完成后取消注释 SSL 块即可。

> 后端镜像构建前需先用清华源预装 `Jinja2` / `typing_extensions`（版本与 requirements.txt 一致）：torch 依赖声明与 pytorch 索引 wheel 元数据大小写/连字符不一致，新版 pip 严格校验会丢弃 wheel 转 sdist 构建而失败（见 `deploy/Dockerfile.backend` 注释）。
