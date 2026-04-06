# 🕷️ my_spider - 数据采集与分析平台 | Data Collection & Analysis Platform

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> 一个集成爬虫、AI 对话、数据可视化的多功能平台 / A multi-functional platform integrating web scraping, AI chat, and data visualization.

---

## 📖 项目简介 | Introduction

**my_spider** 是一个基于 Python 的多功能数据采集与分析平台，提供 Web 和桌面两种交互方式。

**my_spider** is a Python-based multi-functional data collection and analysis platform, providing both Web and Desktop interaction modes.

### ✨ 核心功能 | Core Features

| 模块 | 功能 | 技术栈 |
|------|------|--------|
| 🕷️ **爬虫模块** | Selenium / Playwright 自动化爬取，支持反爬、Cookie 管理 | Selenium, Playwright, requests |
| 🤖 **AI 对话** | 支持 DeepSeek / 豆包模型，工具调用，多模态图片输入 | LangChain, LangGraph, FAISS |
| 📊 **数据分析** | 数据可视化 Dashboard，图表分析，数据导出 | Streamlit, Plotly, Pandas |
| 🖥️ **双端 UI** | Streamlit Web + PyQt6 桌面应用 | Streamlit, PyQt6, QWebEngine |

---

## 🚀 快速开始 | Quick Start

### 1. 安装依赖 | Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. 运行方式 | Run

**方式一：Streamlit Web 模式（推荐）**
```bash
streamlit run streamlit_app.py
```

**方式二：PyQt6 桌面模式**
```bash
python qt_core.py
```

**方式三：独立爬虫入口**
```bash
python main.py
```

### 3. 配置 | Configuration

- **API 密钥**: 在 `utils/sensitive_data.py` 中配置 LLM API Key
- **目标网站**: 在 `spiderlx/core/save/urls.py` 中配置爬取目标

---

## 📁 目录结构 | Directory Structure

```
my_spider/
├── streamlit_app.py      # Streamlit 主应用 / Main Streamlit app
├── qt_core.py            # PyQt6 桌面壳 / PyQt6 desktop shell
├── main.py               # 爬虫入口 / Spider entry point
│
├── spiderlx/             # 🕷️ 爬虫模块 / Spider module
│   ├── auto/web/         #   自动化爬虫 (Selenium + Playwright)
│   ├── ui/               #   Streamlit UI 界面
│   ├── core/             #   核心请求与数据保存
│   └── anti/             #   反爬策略 (Cookie/UA/验证码)
│
├── yuanai/               # 🤖 AI 模块 / AI module
│   ├── core/             #   LLM 调用封装
│   ├── tools/            #   AI 工具 (计算器/天气/RAG)
│   └── ui/               #   聊天界面
│
├── datanalysis/          # 📊 数据分析 / Data analysis
│   ├── ui/               #   可视化 Dashboard
│   └── df/               #   数据处理
│
├── db/                   # 数据库 / Database (SQLite)
├── utils/                # 工具类 / Utilities
└── data/                 # 数据目录 / Data directory
```

---

## 🛠️ 技术栈 | Tech Stack

- **Web UI**: Streamlit
- **Desktop**: PyQt6 + QWebEngine
- **爬虫**: Selenium, Playwright, requests
- **AI**: LangChain, LangGraph, DeepSeek API, 豆包 API
- **RAG**: FAISS + HuggingFace Embeddings
- **可视化**: Plotly, Pandas
- **数据库**: SQLite + SQLAlchemy
- **安全**: cryptography (Fernet/AES-256)

---

## 📝 许可证 | License

MIT License
