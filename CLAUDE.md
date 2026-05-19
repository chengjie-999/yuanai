# 小元AI — 项目入口指南

## 项目概览

前后端分离的 AI 自动化平台，以 AI 对话为统一入口，集成 WEB 自动化、数据采集、屏幕监控。

## 启动方式

```bash
# 后端 API（端口 8000）
python -m api.main

# React 前端（端口 5173）
cd frontend && npm run dev
```

## 目录结构

```
api/                FastAPI 后端（5 个子路由）
spiderlx/           爬虫核心（HTTP / Cookie）
yuanai_core/        核心业务逻辑
├── core/           LangChain 适配层（lc.py, chat.py）
├── pure/           ★ 纯业务逻辑（无框架依赖，任何代码可调用）
├── tools/          @tool 装饰器（自动发现，薄壳调用 pure/）
├── skills/         独立技能（从 pure/ 重新导出）
├── rag.py          向量知识库（Milvus + Embedding，待启用）
└── utils/          工具函数（图片处理等）
config/settings.py  统一配置（模型/JWT/数据库）
db/session.py       SQLAlchemy ORM（MySQL + SQLite）
frontend/           React 18 + TypeScript 前端
data/
├── chat_images/    聊天图片存储（运行时生成，已 gitignore）
├── qimg/           题目截图
├── aiprompt/       知识库文档（待启用）
└── crawl/          爬取原始文件
```

## 技术栈

Python 3.10+ / FastAPI / React 18 / LangChain + LangGraph /
Selenium / Playwright / MySQL / SQLite / Redis（可选）/
DeepSeek API + 豆包 API

## 环境变量

复制 `.env.example` → `.env`，必须配置：
- `JWT_SECRET_KEY` — JWT 签名密钥
- `DEEPSEEK_API_KEY` / `DOUBAO_API_KEY` — AI 模型 API Key
- `MYSQL_PASSWORD` — 数据库密码
- `ENCRYPTION_PASSWORD` — 加密密码

## 聊天多模态

聊天支持图片上传和 AI 生成图片展示：
- 用户上传图片：前端 paste / 文件选择 → base64 → 随消息发送
- AI 生成图片：工具输出中的 `data:image/...` 自动提取，流式推送 `image` 事件
- 图片存储：`data/chat_images/{session_id}/` 下，通过 `/api/v1/chat/image/` 端点访问
- 数据库 `ai_chat` 表新增 `images` 列（JSON 数组）

## AI 工具系统

工具在 `yuanai_core/tools/` 下自动发现（`@tool` 装饰器）。
工具通过 `api/v1/tools/execute` 端点调用，按角色区分权限。

**纯业务逻辑在 `yuanai_core/pure/`**，无框架依赖，任何人可直接调用：

```python
from yuanai_core.pure import add, multiply, fetch_url, parse_html
from yuanai_core.pure import cookies_to_dict, get_system_stats, list_files
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
