# 小元AI — AI 数据分析平台

[![Python](https://img.shields.io/badge/Python-3.10-blue)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-61dafb)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688)](https://fastapi.tiangolo.com/)

前后端分离的 AI 数据分析平台。以 AI 对话为统一入口，支持数据集上传、自动分析、可视化图表生成、AI Agent 工具调用。

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

**后端 API（端口 8000）**：
```bash
python -m api.main
```

**React 前端（端口 5173）**：
```bash
cd frontend
npm run dev
```

### 创建管理员

启动后用 admin 账号登录后台管理页（右上角 👤）→ 用户管理 → **创建用户**，设置角色为 admin。

---

## 功能模块

### 💬 聊天
- 多模型：豆包 Pro/Lite、DeepSeek V4 Flash/Pro
- 多会话管理，按天分组
- Markdown 渲染 + 图片上传/粘贴 + AI 生成图片展示（点击放大）
- 工具调用可视化（按角色过滤）

### 📊 数据分析（核心）
- 上传 CSV/Excel/JSON → 自动解析列信息 → 数据集管理
- **基础分析**：describe 统计、缺失值检测、相关性矩阵（秒级）
- **图表生成**：分布直方图、热力图、箱线图（matplotlib）
- Redis + 文件双缓存，分析结果持久化
- 图表放大/滚轮缩放/拖动平移
- **AI 聊天分析**：对话中直接说"分析数据集 #1"

### 📂 数据工作台
- 上传/删除数据集，全屏预览
- 同名+同大小文件自动查重替换

### 📡 数据采集（仅 admin）
- HTTP 批量请求 + HTML 解析
- 爬取记录管理，结果预览

### 🔧 工具面板
16 个 AI 工具分类展示、在线执行

### 💬 AI 聊天
- 多模型：豆包 / DeepSeek
- SSE 流式输出 + Markdown 渲染
- 图片上传/粘贴 + 工具调用可视化

### ⚙ 后台管理（仅 admin）
- 用户管理：创建/冻结/删除
- 网站管理 + 文件管理
- 系统统计：用户数、会话数、消息趋势

---

## 权限系统

| 角色  | 聊天 | 数据分析 | 数据工作台 | 数据采集 | 后台管理 |
|-------|------|---------|-----------|---------|---------|
| admin | ✅   | ✅      | ✅        | ✅      | ✅      |
| user  | ✅   | ✅      | ✅        | ❌      | ❌      |

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

### 爬虫（仅 admin）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/spider/save/record` | 保存采集记录 |
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

frontend/               React 18 + TypeScript 前端
├── src/components/
│   ├── ChatPage.tsx        聊天
│   ├── BrowserPage.tsx     WEB自动化
│   ├── DataCollectionPage.tsx  数据采集
│   ├── ToolsPage.tsx       工具面板
│   ├── DataAnalysisPage.tsx 数据分析
│   ├── AdminPage.tsx       后台管理
│   ├── SettingsPage.tsx    系统设置
│   └── LoginPage.tsx       登录

spiderlx/               爬虫核心
├── core/requests/      HTTP 请求（含反爬）
├── core/save/          数据保存
└── anti/               Cookie / UA

yuanai_core/            核心业务逻辑
├── core/               LangChain 适配层（lc.py, chat.py）
├── pure/               ★ 纯业务逻辑（无框架依赖，任何代码可调用）
├── tools/              @tool 装饰器（自动发现，薄壳调用 pure/）
├── skills/             独立技能（从 pure/ 重新导出）
├── rag.py              向量知识库（Milvus + Embedding，待启用）
└── utils/              工具函数（图片处理等）

config/settings.py      统一配置（模型/JWT/数据库）
db/session.py           SQLAlchemy ORM（MySQL + SQLite）
data/
├── chat_images/        聊天图片存储（运行时生成）
├── crawl/              爬取原始文件
├── qimg/               题目截图
├── aiprompt/           知识库文档（待启用）
└── web_cookie/         第三方网站 Cookie
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python, FastAPI, Uvicorn, LangChain, LangGraph, SQLAlchemy |
| 前端 | React 18, TypeScript, Vite |
| 数据库 | MySQL 8.0, SQLite, Redis（可选） |
| 爬虫 | requests, BeautifulSoup |
| AI | DeepSeek API, 豆包 API |
| 鉴权 | python-jose (JWT), bcrypt |
| 配置 | `config/settings.py` 统一管理 |
| 业务层 | `yuanai_core/pure/` 纯 Python，无框架依赖 |
