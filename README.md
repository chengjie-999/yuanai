# yuanai — AI 自动化平台

[![Python](https://img.shields.io/badge/Python-3.10-blue)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-61dafb)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com/)

前后端分离的 AI 自动化平台。以 AI 对话为统一入口，集成 WEB 自动化、屏幕监控、工具执行等功能。

---

## 快速开始

### 环境

- Python 3.10+
- Node.js 18+
- MySQL 8.0+

### 安装

```bash
pip install -r requirements.txt
cd frontend
npm install && cd ..
```

### 初始化数据库

```sql
CREATE DATABASE ai_agent DEFAULT CHARSET utf8mb4;
```

### 启动

**后端**（终端 1）：
```bash
python -m api.main
```

**前端**（终端 2）：
```bash
cd frontend
npm run dev
```

### 创建管理员

打开前端 http://localhost:5173 → 注册 tab → 创建账号后到数据库执行：

```sql
UPDATE users SET role = 'admin' WHERE username = '你的用户名';
```

重启后端生效。

---

## 功能模块

### 💬 聊天
- 多模型：豆包 Pro/Lite、DeepSeek V4 Flash/Pro
- 多会话管理，按天分组
- Markdown 渲染 + 图片上传
- 工具调用可视化

### 🌐 WEB 自动化

三步骤流程：

| 步骤 | 操作 |
|------|------|
| 1. 打开网站 | 启动浏览器、快捷网址、Cookie 管理 |
| 2. 开始任务 | 查看任务列表、选择任务 |
| 3. 执行任务 | 获取题目、AI 审核、滚动/缩放、提交/驳回 |

支持：小猿众包单题标答审核工作流、参考答案展示、AI Agent 自动审核。

### 🔧 工具面板
- 30+ 工具分类展示、搜索、在线执行

### 📺 全局状态实时监控
- mss 屏幕截图，SSE 实时推流
- 多显示器切换，帧率可调（10ms - 600ms）
- 开始/停止控制

---

## 权限系统

| 角色 | 聊天 | 工具查看 | 工具执行 | 浏览器控制 | 监控 |
|------|------|---------|---------|-----------|------|
| admin | ✅ | ✅ | ✅ | ✅ | ✅ |
| user | ✅ | ✅ | ❌ | ❌ | ✅ |

- 登录后 JWT Token 存在 localStorage，请求自动带 `Authorization` header
- Token 有效期 7 天
- 未登录返回 401，权限不足返回 403

### 公开路径（免登录）

```
/                         健康检查
/api/v1/auth/*            注册、登录、Token 验证
/api/v1/qimg/*            题目截图静态文件
/api/v1/monitor/*         屏幕监控（只读）
/api/v1/browser/stream    自动化截图流（只读）
```

---

## API 概览

### 鉴权

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册 |
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

### 工具

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/v1/tools/` | 所有用户 | 工具列表 |
| POST | `/api/v1/tools/execute` | admin | 执行工具 |

### 浏览器

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/api/v1/browser/start` | admin | 启动 |
| POST | `/api/v1/browser/stop` | admin | 关闭 |
| GET | `/api/v1/browser/status` | 所有用户 | 状态 |
| GET | `/api/v1/browser/screenshot` | 所有用户 | 截图 |
| GET | `/api/v1/browser/stream` | 公开 | SSE 推流 |

### 监控

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/monitor/screenshot` | 屏幕截图 |
| GET | `/api/v1/monitor/monitors` | 显示器列表 |
| GET | `/api/v1/monitor/stream` | SSE 推流 |

---

## 目录结构

```
api/                  FastAPI 后端
├── main.py           入口 + CORS + 静态文件
└── v1/
    ├── auth/         账号注册登录
    ├── chat/         聊天 SSE
    ├── tools/        工具管理
    ├── browser/      浏览器控制
    ├── monitor/      屏幕监控
    ├── spider/       爬虫
    ├── middleware.py JWT 中间件
    └── models.py     数据模型

frontend/             React 前端
├── src/
│   ├── components/
│   │   ├── ChatPage.tsx
│   │   ├── BrowserPage.tsx
│   │   ├── ToolsPage.tsx
│   │   ├── MonitorPage.tsx
│   │   ├── LoginPage.tsx
│   │   ├── MarkdownContent.tsx
│   │   ├── ToolCallCard.tsx
│   │   ├── ModelSelector.tsx
│   │   └── browser/   StepBar / Step1Content / helpers
│   └── api/index.ts

spiderlx/             爬虫模块
├── auto/web/         Selenium + Playwright
├── core/             浏览器管理器、HTTP 请求、数据保存
└── anti/             Cookie / IP / UA / CDP

yuanai/               AI 模块
├── core/lc.py        LLM 配置
├── core/chat.py      Agent 流式调用
├── tools/            30+ 工具
└── audit/            审核流程

db/                   数据库层
├── session.py        SQLAlchemy ORM
├── redis_client.py   Redis 连接
└── cache.py          Redis 缓存

data/                 运行数据
├── qimg/             题目截图
└── aiprompt/         标注规范
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python, FastAPI, Uvicorn, LangChain, LangGraph, SQLAlchemy |
| 前端 | React 18, TypeScript, Vite, react-markdown |
| 数据库 | MySQL 8.0, Redis |
| 爬虫 | Selenium, Playwright, PyAutoGUI |
| AI | DeepSeek API, 豆包 API |
| 鉴权 | python-jose (JWT), bcrypt |
| 加密 | cryptography (Fernet / AES-256) |

---

## 配置

| 配置项 | 位置 |
|--------|------|
| DeepSeek / 豆包 API Key | `yuanai/core/lc.py` |
| MySQL 密码 | `utils/sensitive_data.py`（加密） |
| JWT 密钥 | `api/v1/auth/utils.py` |
| 标注规范 | `data/aiprompt/annotation_spec.txt` |
