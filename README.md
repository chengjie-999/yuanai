# 🕷️ my_spider - 数据采集与分析平台

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)

> 集成爬虫、AI 对话、AI 审核、数据可视化的多功能平台

---

## 📖 项目简介

基于 Python 的多功能平台，提供 **Streamlit Web UI** 和 **PyQt6 桌面壳** 两种交互方式。

### 核心功能

| 模块 | 功能 | 技术栈 |
|------|------|--------|
| 🕷️ **爬虫** | Selenium / Playwright 自动化爬取，Cookie 管理，反爬 | Selenium, Playwright |
| 🤖 **AI 对话** | DeepSeek / 豆包大模型，工具调用，多模态图片输入 | LangChain, LangGraph |
| 🎯 **AI 审核** | 题目标注自动审核，Agent 自动化操作，人工反馈闭环 | LangGraph Agent + 人机协作 |
| 📊 **数据分析** | 可视化 Dashboard，Plotly 图表，CSV/Excel 分析 | Streamlit, Plotly |
| 🖥️ **双端 UI** | Streamlit Web + PyQt6 桌面 | Streamlit, PyQt6 |

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
cd frontend && npm install --registry=https://registry.npmmirror.com
```

### 2. 启动

需要分别启动 **API 后端** 和 **前端** 两个服务。

**终端1：FastAPI 后端**
```bash
uvicorn api.main:app --reload --port 8000
```
API 文档：http://localhost:8000/docs

**终端2：React 前端（新）**
```bash
cd frontend && npm run dev
```
前端页面：http://localhost:5173

**终端3（过渡期）：Streamlit 旧 UI**
```bash
streamlit run streamlit_app.py
```

> 等前端开发完成后，前端构建产物会嵌入 FastAPI 静态服务，届时只需启动终端1即可。

### 3. 环境说明

- 建议使用 **Windows PowerShell** 运行所有命令
- Node.js 版本需 >= 18（推荐 22 LTS）
- API 端口 8000，前端端口 5173

---

---

## 📁 目录结构

```
my_spider/
├── streamlit_app.py         # Streamlit 主应用入口
├── qt_core.py               # PyQt6 桌面壳
├── main.py                  # 爬虫 CLI 入口
│
├── spiderlx/                # 🕷️ 爬虫模块
│   ├── auto/
│   │   ├── web/
│   │   │   ├── selenium/    # Selenium 浏览器自动化
│   │   │   │   ├── main.py         # 浏览器初始化、反爬、Cookie
│   │   │   │   └── xiaoyuan/       # 小猿众包平台自动化
│   │   │   └── playwrightdo/       # Playwright 自动化
│   │   └── canvas/          # ✨ 画布物理操作（pyautogui）
│   │       └── core.py      #   scroll / click 操作
│   ├── core/                # HTTP 请求、数据保存
│   ├── anti/                # 反爬（Cookie / IP / UA）
│   └── ui/                  # Streamlit 爬虫 UI
│       └── selenium/
│           ├── uixiaoyuan.py      # 小猿任务 UI + AI 审核流
│           └── uiselenium.py      # 通用浏览器 UI
│
├── yuanai/                  # 🤖 AI 模块
│   ├── core/
│   │   ├── lc.py            # LLM 配置（DeepSeek / 豆包）
│   │   └── chat.py          # 消息构建、Agent 流式调用
│   ├── tools/               # AI 工具（@tool 自动发现）
│   │   ├── calculator.py
│   │   ├── weather.py
│   │   ├── audit_tools.py   # 审核工具（检索规范/保存反馈）
│   │   └── selenium_tools/  # 浏览器自动化工具（AI Agent 用）
│   │       ├── core.py      #   浏览器管理工具
│   │       └── xiaoyuan.py  #   小猿平台操作工具（14个）
│   ├── audit/
│   │   ├── core.py          # 审核核心 + 流程编排 + prompt 构建
│   │   ├── parser.py        # 审核结果解析
│   │   └── ui.py            # 审核结果格式化
│   ├── rag.py               # 规范检索（分段匹配，无 RAG 依赖）
│   └── ui/
│       ├── ai.py            # AI 聊天主界面
│       └── components.py    # UI 组件
│
├── datanalysis/             # 📊 数据分析
│   ├── ui/                  # 数据 Dashboard
│   ├── df/                  # 数据处理
│   └── visualize/           # 图表生成
│
├── api/                     # FastAPI REST 接口
│   └── v1/spider/           # 爬虫请求/保存接口
│
├── webui/                   # Streamlit 状态管理
├── db/                      # SQLite 数据库
├── utils/                   # 工具类（路径/密钥/视频处理）
└── data/                    # 数据目录
    ├── aiprompt/            # 标注规范（annotation_spec.txt）
    ├── user/from/           # 用户导入数据
    └── user/to/             # 处理结果输出
```

---

## 🎯 AI 审核工作流

### 全自动流程

```
用户点击 "AI审核"
  │
  ├─ Agent 启动
  │   ├─ scroll_canvas()    # 滚动查看完整题目
  │   ├─ zoom_question()    # 缩小视图
  │   └─ scroll/zoom 后自动截图注入，继续分析
  │
  ├─ mark_question_correct()  # 自动处理标准判定
  │
  └─ 输出审核结论
  │
  └─ 用户反馈
      ├─ ✅ 正确 → 自动提交下一任务
      ├─ ❌ 纠正 → 输入原因 → 自动驳回
      └─ ⏭ 跳过
```

### 审核 Agent 工具

| 工具 | 功能 |
|------|------|
| `scroll_canvas` | pyautogui 滚动画布 |
| `click_canvas` | pyautogui 点击坐标 |
| `zoom_question` | 缩小题目视图 |
| `restore_question_view` | 恢复视图 |
| `mark_question_correct` | 标记审核正确 |
| `get_question_info` | 获取截图信息 |
| `submit_task` | 提交或驳回任务 |
| `confirm_rejection` | 确认驳回弹窗 |
| `retrieve_annotation_spec` | 检索标注规范 |
| `save_audit_feedback` | 保存反馈 |

### 分层 Prompt 设计

```
第1层: 规则注入 → 按关键词匹配 annotation_spec.txt 相关段落
第2层: 操作指令 → 指导 Agent 如何滚动/缩放/标记
第3层: 工具可用 → 所有 @tool 工具可被 Agent 调用
第4层: 决策输出 → 用户确认反馈闭环
```

---

## 🛠️ 技术栈

- **Web UI**: Streamlit
- **桌面**: PyQt6 + QWebEngine
- **爬虫**: Selenium, Playwright, requests
- **AI**: LangChain, LangGraph, DeepSeek API, 豆包 API (Volcengine)
- **规范检索**: 标题正则分段 + 关键词匹配
- **可视化**: Plotly, Pandas
- **数据库**: SQLite + SQLAlchemy
- **安全**: cryptography (Fernet/AES-256)

---

## 🔧 配置

| 配置项 | 位置 | 说明 |
|--------|------|------|
| LLM API Key | `utils/sensitive_data.py` | DeepSeek 密钥解密 |
| 豆包 API Key | `yuanai/core/lc.py` | 硬编码（需更新） |
| 目标网站 | `spiderlx/core/save/urls.py` | 爬取目标配置 |
| 标注规范 | `data/aiprompt/annotation_spec.txt` | 审核规则 |
| 数据库 | `agent.db` | 自动创建 |

---

## 📝 许可证

MIT License
