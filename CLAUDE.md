# 小元AI — 项目入口指南

## 项目概览

前后端分离的 AI 数据分析平台，以 AI 对话为统一入口，集成数据上传、自动分析、可视化图表。

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
│   └── analysis.py   数据分析引擎（pandas + matplotlib）
├── tools/          @tool 装饰器（自动发现，16 个工具）
├── skills/         独立技能（从 pure/ 重新导出）
├── rag.py          向量知识库（Milvus + Embedding，待启用）
└── utils/          工具函数（图片处理等）
config/settings.py  统一配置（模型/JWT/数据库）
db/session.py       SQLAlchemy ORM（MySQL）
frontend/           React 18 + TypeScript 前端
data/
├── datasets/       上传的数据集文件
├── analysis/       分析结果 + 图表 PNG 缓存
├── chat_images/    聊天图片（运行时生成）
├── aiprompt/       知识库文档（待启用）
└── crawl/          爬取原始文件
```

## 技术栈

Python 3.10+ / FastAPI / React 18 / LangChain + LangGraph /
MySQL / Redis / Pandas / Matplotlib / Docker

## 数据分析系统

**数据管理：**
- 上传 CSV/Excel/JSON → `data/datasets/`，自动解析列信息 + 前 100 行预览
- 同名+同大小文件查重替换，更新上传时间
- 前端：数据集列表 + 全屏预览弹窗

**分析引擎：**
- `yuanai_core/pure/analysis.py` — 共享分析核心，纯函数无框架依赖
- 基础分析：describe 统计、缺失值、相关性矩阵（pandas，秒级）
- 图表分析：分布直方图、相关性热力图、箱线图（matplotlib，多进程）

**缓存策略：**
- Redis + 本地文件双缓存，基础/图表分 key 互不覆盖
- 分析结果 JSON 持久化到 `data/analysis/{id}/result_*.json`
- 图表 PNG 存 `data/analysis/{id}/*.png`，URL 返回不塞响应体

**性能：**
- CPU 密集（pandas/matplotlib）→ `ProcessPoolExecutor` 多进程
- IO 密集（数据库/文件）→ `asyncio.to_thread` 多线程
- `get_db()` 单例模式，避免重复创建连接池
- `asyncio.shield()` 防止客户端断开取消正在进行的分析

## AI 工具系统

工具在 `yuanai_core/tools/` 下自动发现（`@tool` 装饰器），16 个工具。
AI Agent 通过 SSE 流式返回结果，工具输出的 `data:image/...` 自动提取为图片。

**数据分析工具：**
- `list_datasets` — 列出所有数据集
- `preview_dataset` — 预览数据集前 10 行
- `analyze_dataset` — pandas 统计 + matplotlib 图表

**通用工具：**
- `calculate_sum` / `calculate_multiply` — 精确计算
- `fetch_url` / `parse_html` — 网页抓取
- `get_today_temperature` / `get_tomorrow_forecast` — 天气
- `get_system_stats` — 系统统计
- `save_data_csv` / `list_data_files` / `read_data_file` — 文件管理
- `save_crawl_data` / `list_crawl_data` / `get_crawl_detail` — 爬取记录

## 权限

| 角色  | 聊天 | 数据分析 | 数据工作台 | 数据采集 | 后台管理 |
|-------|------|---------|-----------|---------|---------|
| admin | ✅   | ✅      | ✅        | ✅      | ✅      |
| user  | ✅   | ✅      | ✅        | ❌      | ❌      |

## 安全须知

- `.env` 已被 gitignore，永不提交
- API Key / 密钥从环境变量读取，不在源码硬编码
- URL 爬取有 SSRF 防护（内网地址拦截）
- 数据操作有所有权校验（用户只能操作自己的数据）
- JWT 鉴权中间件统一验证
