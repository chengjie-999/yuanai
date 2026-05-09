# 小元AI — AI 自动化平台

[![Python](https://img.shields.io/badge/Python-3.10-blue)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-61dafb)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com/)

前后端分离的 AI 自动化平台。以 AI 对话为统一入口，集成 WEB 自动化、数据采集、屏幕监控、工具执行等功能。

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

**后端**：
```bash
python -m api.main
```

**前端**：
```bash
cd frontend && npm run dev
```

### 创建管理员

启动后用 admin 账号登录后台管理页（右上角 👤）→ 用户管理 → **创建用户**，设置角色为 admin。

---

## 功能模块

### 💬 聊天
- 多模型：豆包 Pro/Lite、DeepSeek V4 Flash/Pro
- 多会话管理，按天分组
- Markdown 渲染 + 图片上传
- 工具调用可视化（按角色过滤）

### 🌐 WEB 自动化
三步流程：打开网站 → 选择任务 → AI 自动审核。支持小猿众包审核工作流、参考答案展示、自然语言指令控制。

### 📡 数据采集
- HTTP GET/POST 请求，支持 Cookie 登录态
- **批量爬取**：多 URL 同时请求，自动查重
- **反爬**：随机 UA、请求延迟 1-3s、失败重试
- **HTML 解析**：BeautifulSoup 提取标题/正文/链接，结果持久化
- **历史记录**：分页查看、重新解析、原始文件预览
- **AI 工具**：fetch_url、parse_html、save_crawl_data 等 5 个工具

### 🔧 工具面板
35+ 工具分类展示、搜索、在线执行。浏览器类工具灰显为仅 admin 可用。

### 📺 全局状态实时监控
mss 屏幕截图，SSE 实时推流，多显示器切换，帧率可调。

### 📊 数据分析
系统真实数据统计：用户数、会话数、消息趋势、审核记录、缓存占用。

### ⚙ 后台管理
- **用户管理**：创建/冻结/删除用户（仅 admin）
- **网站管理**：添加/删除爬取目标网站
- **文件管理**：浏览 data/ 目录，双击预览文件

---

## 权限系统

| 角色 | 聊天 | 工具查看 | 工具执行 | 浏览器控制 | 监控 |
|------|------|---------|---------|-----------|------|
| admin | ✅ | ✅ | ✅ | ✅ | ✅ |
| user | ✅ | ✅ | ❌ | ❌ | ✅ |

- JWT Token 存储在 localStorage，有效期 7 天
- 注册功能已关闭，仅 admin 可创建用户
- 用户可被冻结，冻结期间无法使用

### 公开路径

```
/                      健康检查
/health                健康检查
/api/v1/qimg/*         静态文件
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

### 爬虫
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/spider/request/request` | 单条请求 |
| POST | `/api/v1/spider/request/batch` | 批量请求 |
| GET | `/api/v1/spider/request/parse` | HTML 解析 |
| GET | `/api/v1/spider/request/cookies` | Cookie 文件列表 |
| POST | `/api/v1/spider/save/record` | 保存记录 |
| GET | `/api/v1/spider/save/records` | 记录列表 |
| DELETE | `/api/v1/spider/save/record/{id}` | 删除记录 |
| GET | `/api/v1/spider/save/record/{id}/file` | 读取原始文件 |

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
| GET | `/api/v1/browser/stream` | 需登录 | SSE 推流 |

### 监控
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/monitor/screenshot` | 屏幕截图 |
| GET | `/api/v1/monitor/stream` | SSE 推流 |

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
| GET | `/api/v1/admin/files` | 文件列表 |
| GET | `/api/v1/admin/file/read` | 读取文件 |

---

## 目录结构

```
api/                    FastAPI 后端
├── main.py             入口
└── v1/
    ├── auth/           用户认证
    ├── chat/           聊天 SSE
    ├── tools/          工具管理
    ├── browser/        浏览器控制
    ├── monitor/        屏幕监控
    ├── spider/         爬虫请求/保存
    ├── admin/          后台管理
    ├── stats/          系统统计
    ├── middleware.py   JWT 中间件
    └── models.py       数据模型

frontend/               React 前端
├── src/components/
│   ├── ChatPage.tsx        聊天
│   ├── BrowserPage.tsx     WEB自动化
│   ├── DataCollectionPage.tsx  数据采集
│   ├── ToolsPage.tsx       工具面板
│   ├── MonitorPage.tsx     屏幕监控
│   ├── DataAnalysisPage.tsx 数据分析
│   ├── AdminPage.tsx       后台管理
│   ├── SettingsPage.tsx    系统设置
│   ├── LoginPage.tsx       登录
│   └── browser/            StepBar / Step1Content

spiderlx/               爬虫模块
├── core/requests/      HTTP 请求（含反爬）
├── core/save/          数据保存
├── anti/               Cookie / IP / UA
└── auto/               Selenium / Playwright

yuanai/                 AI 模块
├── core/lc.py          LLM 配置
├── core/chat.py        Agent 流式调用
├── tools/              35+ 工具（自动发现）
└── audit/              审核流程

config/settings.py      统一配置（模型/JWT/数据库）
db/session.py           SQLAlchemy ORM
data/
├── crawl/              爬取原始文件
├── qimg/               题目截图
└── web_cookie/         第三方网站 Cookie
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python, FastAPI, Uvicorn, LangChain, LangGraph, SQLAlchemy |
| 前端 | React 18, TypeScript, Vite, react-markdown |
| 数据库 | MySQL 8.0, Redis |
| 爬虫 | Selenium, Playwright, BeautifulSoup, requests |
| AI | DeepSeek API, 豆包 API |
| 鉴权 | python-jose (JWT), bcrypt |
| 配置 | `config/settings.py` 统一管理 |
