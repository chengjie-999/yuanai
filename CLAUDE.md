# 小元AI — 项目入口指南

## 项目概览

前后端分离的 AI 自动化平台，以 AI 对话为统一入口，集成 WEB 自动化、数据采集、屏幕监控。

## 启动方式

```bash
# 后端 API（端口 8000）
python -m api.main

# Streamlit UI（端口 8501）
streamlit run streamlit_app.py

# React 前端（端口 5173）
cd frontend && npm run dev

# Qt 桌面客户端
python qt_core.py
```

## 目录结构

```
api/                FastAPI 后端（8 个子路由）
spiderlx/           爬虫核心（HTTP / Selenium / Playwright）
yuanai/             AI 引擎（LangChain + LangGraph Agent + 48 个工具）
config/settings.py  统一配置（模型/JWT/数据库）
db/session.py       SQLAlchemy ORM（MySQL + SQLite）
frontend/           React 18 + TypeScript 前端
webui/              Streamlit 状态管理
streamlit_app.py    Streamlit 主入口
```

## 技术栈

Python 3.10+ / FastAPI / Streamlit / React 18 / LangChain + LangGraph /
Selenium / Playwright / MySQL / SQLite / Redis（可选）/
DeepSeek API + 豆包 API

## 环境变量

复制 `.env.example` → `.env`，必须配置：
- `JWT_SECRET_KEY` — JWT 签名密钥
- `DEEPSEEK_API_KEY` / `DOUBAO_API_KEY` — AI 模型 API Key
- `MYSQL_PASSWORD` — 数据库密码
- `ENCRYPTION_PASSWORD` — 加密密码

## AI 工具系统

工具在 `yuanai/tools/` 下自动发现（`@tool` 装饰器），48 个工具分 11 个模块。
工具通过 `api/v1/tools/execute` 端点调用，按角色区分权限。

无状态的纯函数工具已提取到 `yuanai/skills/`，可脱离 LangChain 直接 import：

```python
from yuanai.skills.calculator import add, multiply
from yuanai.skills.crawler import fetch_url, parse_html
from yuanai.skills.stats import get_system_stats
```

## 权限

| 角色  | 聊天 | 工具查看 | 工具执行 | 浏览器控制 | 监控 |
|-------|------|---------|---------|-----------|------|
| admin | ✅   | ✅      | ✅      | ✅        | ✅   |
| user  | ✅   | ✅      | ❌      | ❌        | ✅   |

## 安全须知

- `.env` 已被 gitignore，永不提交
- API Key / 密钥从环境变量读取，不在源码硬编码
- URL 爬取有 SSRF 防护（内网地址拦截）
- 会话/浏览器端点有所有权校验
