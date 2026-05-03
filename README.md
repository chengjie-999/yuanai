# my_spider - 数据采集与分析平台

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-61dafb)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com/)

> 集成爬虫、AI 对话、AI 审核、数据分析的多功能平台。前后端分离架构。

---

## 📖 项目简介

基于 Python + React 的**前后端分离**平台。后端 FastAPI 提供 REST + SSE 接口，前端 React + Vite。

### 核心功能

| 模块 | 功能 | 技术栈 |
|------|------|--------|
| 🤖 **AI 对话** | 多模型（豆包/DeepSeek），多会话，Markdown 渲染，工具调用 | LangChain, LangGraph |
| 🕷️ **爬虫** | Selenium / Playwright 自动化，Cookie 管理，反爬 | Selenium, Playwright |
| 🎯 **AI 审核** | 题目标注自动审核，Agent 流式操作，人机反馈闭环 | LangGraph Agent |
| 🔧 **工具面板** | 34 个 @tool 工具的列表、参数输入、在线执行 | FastAPI + React |
| 📊 **数据分析** | 可视化 Dashboard，Plotly 图表（开发中） | Plotly, Pandas |
| 🗄️ **数据库** | MySQL + SQLite 双存储，密码加密 | SQLAlchemy, PyMySQL |

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- Node.js >= 18（推荐 22 LTS）
- MySQL 8.0+（可选，默认 SQLite）

### 2. 安装依赖

```bash
# Python 后端
pip install -r requirements.txt

# React 前端
cd frontend && npm install --registry=https://registry.npmmirror.com
```

### 3. 启动

**终端1：FastAPI 后端**
```bash
uvicorn api.main:app --reload --port 8000
```
API 文档：http://localhost:8000/docs

**终端2：React 前端**
```bash
cd frontend && npm run dev
```
前端页面：http://localhost:5173

**终端3（过渡期）：Streamlit 旧 UI**
```bash
streamlit run streamlit_app.py
```

### 4. MySQL 配置（可选）

```sql
CREATE DATABASE ai_agent DEFAULT CHARSET utf8mb4;
```

在 `utils/sensitive_data.py` 中配置加密后的密码。

---

## 📁 目录结构

```
my_spider/
├── api/                     # FastAPI 后端
│   ├── main.py              # 入口 + CORS
│   └── v1/
│       ├── chat/            # SSE 流式聊天、会话管理
│       ├── tools/           # 工具列表、工具执行
│       └── spider/          # 爬虫请求/保存
│
├── frontend/                # React 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatPage.tsx       # 聊天页面（会话 + 双栏布局）
│   │   │   ├── ToolsPage.tsx      # 工具面板
│   │   │   ├── MarkdownContent.tsx # Markdown 渲染
│   │   │   ├── ToolCallCard.tsx    # 工具调用卡片
│   │   │   └── ThinkingBlock.tsx   # 思考过程展示
│   │   └── api/index.ts           # API 客户端
│   └── vite.config.ts             # Vite + proxy 配置
│
├── spiderlx/                # 🕷️ 爬虫模块
│   ├── auto/
│   │   ├── web/
│   │   │   ├── selenium/    # Selenium 浏览器自动化
│   │   │   └── playwrightdo/# Playwright 自动化
│   │   └── canvas/          # 画布物理操作（pyautogui）
│   ├── core/                # HTTP 请求、数据保存
│   ├── anti/                # 反爬（Cookie / IP / UA / CDP）
│   └── ui/                  # Streamlit 爬虫 UI（过渡期）
│
├── yuanai/                  # 🤖 AI 模块
│   ├── core/
│   │   ├── lc.py            # LLM 配置（DeepSeek / 豆包）
│   │   └── chat.py          # 消息构建、Agent 流式调用
│   ├── tools/               # 35 个 @tool 自动发现
│   │   ├── calculator.py    # 计算工具
│   │   ├── weather.py       # 天气查询
│   │   ├── audit_tools.py   # 审核工具
│   │   └── selenium_tools/  # 浏览器自动化工具（16 个）
│   ├── audit/               # 审核核心 + 流程编排
│   ├── rag.py               # 规范检索
│   └── ui/                  # Streamlit UI（过渡期）
│
├── db/                      # 数据库（SQLAlchemy ORM）
├── utils/                   # 工具类（路径/密钥加密/CDP）
└── data/                    # 数据目录
    ├── aiprompt/            # 标注规范（annotation_spec.txt）
    └── user/                # 用户数据
```

---

## 📡 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/chat/stream` | POST | SSE 流式聊天 |
| `/api/v1/chat/session/new` | POST | 创建新会话 |
| `/api/v1/chat/sessions` | GET | 会话列表 |
| `/api/v1/chat/session/{id}` | DELETE | 删除会话 |
| `/api/v1/chat/messages` | POST | 获取消息 |
| `/api/v1/chat/save` | POST | 保存消息 |
| `/api/v1/tools/` | GET | 工具列表 |
| `/api/v1/tools/execute` | POST | 执行工具 |

---

## 💬 聊天功能

- **多会话管理** — 左侧栏切换、新建、删除
- **Markdown 渲染** — 代码块、表格、链接、图片
- **工具调用可视化** — 彩色状态卡片、执行动画
- **思考过程展示** — 折叠展示 AI 推理过程
- **模型选择** — 豆包 Pro/Lite、DeepSeek V4 Flash/Pro
- **聊天记录持久化** — 自动保存到 MySQL
- **对话导出** — 纯文本下载

---

## 🎯 AI 审核工作流

```
点击 "AI审核"
  │
  ├─ Agent 启动
  │   ├─ scroll_canvas()     # 滚动查看完整题目
  │   ├─ zoom_question()     # 缩小视图
  │   └─ 自动截图注入，继续分析
  │
  ├─ mark_question_correct()  # 自动处理判定
  │
  └─ 输出审核结论 → 用户反馈
      ├─ ✅ 正确 → 提交下一任务
      ├─ ❌ 纠正 → 输入原因 → 驳回
      └─ ⏭ 跳过
```

---

## 🛠️ 技术栈

- **后端**: Python, FastAPI, LangChain, LangGraph, SQLAlchemy
- **前端**: React 18, TypeScript, Vite, react-markdown
- **爬虫**: Selenium, Playwright, pyautogui
- **AI**: DeepSeek API, 豆包 API (Volcengine)
- **数据库**: MySQL 8.0 + SQLite (双存储)
- **安全**: cryptography (Fernet/AES-256)

---

## 🔧 配置

| 配置项 | 位置 | 说明 |
|--------|------|------|
| DeepSeek API Key | `utils/sensitive_data.py` | 加密存储 |
| 豆包 API Key | `yuanai/core/lc.py` | Volcengine Ark |
| MySQL 密码 | `utils/sensitive_data.py` | 加密存储 |
| 标注规范 | `data/aiprompt/annotation_spec.txt` | 审核规则 |
| 目标网站 | `spiderlx/core/save/urls.py` | 爬取目标 |

---

## 📝 许可证

MIT License
