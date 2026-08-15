# 小元AI — 云边协同多智能体平台

## 项目概览

前后端分离的多智能体协作平台，以对话为统一入口，集成数据分析、数据采集、浏览器自动化。Web 运行在云服务器（火山引擎），本地 Agent 负责实际任务执行。统筹 Agent（Orchestrator）自动识别意图并委派专业子 Agent 处理。

## 启动方式

```bash
# 云端 API（端口 8000）
python -m api.main

# React 前端（端口 5173）
cd frontend && npm run dev

# 本地 Agent（命令行模式，开发调试用）
python -m agent.main --agent-id 1

# 本地 Agent（托盘模式，发布用）
python -m agent.main --agent-id 1 --tray
```

## 多智能体架构

```
用户 → Web 对话界面 → SSE → FastAPI → WebSocket → 本地 Agent
                                                        │
                                              统筹 Agent（意图路由）
                                             ┌──────┼──────┐
                                        数据分析  数据采集  自动化
                                         Agent    Agent    Agent
```

**Agent 模型分配：**

| Agent | 模型 | 职责 |
|-------|------|------|
| 统筹 | doubao-seed-2-0-lite | 意图识别 + 任务路由 |
| 数据分析 | doubao-seed-2-0-pro | 数据集管理、统计、图表 |
| 数据采集 | doubao-seed-2-0-lite | 网页爬取、数据抓取 |
| 自动化 | doubao-seed-2-0-pro | 浏览器控制、题目审核、截图监控 |

## 目录结构

```
api/                    FastAPI 后端
├── main.py             应用入口（CORS、路由注册）
└── v1/
    ├── chat/router.py      SSE 对话 + Agent WebSocket 桥接
    ├── agent/router.py     WebSocket Hub（Agent 注册/心跳/中继）
    ├── admin/router.py     后台管理 API（仪表盘/用户/Agent状态/模型配置）
    ├── auth/               JWT 认证
    ├── data/               数据集管理
    ├── knowledge/           知识库
    ├── analysis/           分析大屏 API（RFM、dashboard 数据服务）
    ├── monitor/           代码进度实时监控（Git 轮询 + 可视化仪表盘）
    └── ...
agent/                  本地 Agent 运行时 ★
├── main.py              入口（--tray 托盘 / 默认命令行）
├── orchestrator.py      统筹 Agent（动态 delegate 工具，从 skills/ 自动发现）
├── ws_client.py         WebSocket 客户端（自动重连）
├── tray.py              系统托盘程序（pystray）
├── verify.py            多智能体链路验证脚本
├── yuanai_agent.spec    PyInstaller 打包规格
├── agents/              子 Agent
│   ├── analysis.py      数据分析子 Agent
│   ├── collection.py    数据采集子 Agent
│   └── automation.py    自动化子 Agent
├── tools/               Agent 专用工具（38 个）
│   ├── selenium_tools/  浏览器自动化
│   ├── audit_tools.py   审核知识库 + 反馈
│   └── ...
├── datanalysis/         数据分析脚本目录
│   ├── scripts/          独立分析脚本（Agent 自动发现，9个）
│   │   ├── 描述性统计分析.py   统计 + 图表（matplotlib/seaborn/plotly）
│   │   ├── 相关性分析.py       相关系数 + 热力图/聚类图/散点矩阵
│   │   ├── 数据预处理.py       缺失值 + 异常值 + 标准化 + 特征选择
│   │   ├── 时间序列分析.py     STL分解 + ADF检验 + 滚动统计
│   │   ├── 回归分析.py         线性/岭/Lasso + 交叉验证
│   │   ├── 分类数据分析.py     卡方检验 + 小提琴图/树图
│   │   ├── RFM客户分群.py     客户分群 + 3D散点（内置示例数据）
│   │   ├── 客户流失预测.py     逻辑回归 + ROC + CV
│   │   └── bio_analysis.py    基因表达 + 火山图
│   └── crawl/             网页采集脚本
├── audit/               AI 审核系统（题目判定 + 结果解析）
└── rag.py               Milvus Lite 向量知识库
yuanai_core/            公共核心库（云边共用）
├── core/
│   ├── lc.py            LLM 工厂（DeepSeek / 豆包）
│   ├── chat.py          Agent 编排（DeepSeek V4 专用 + LangGraph 通用）
│   └── schemas.py       消息协议（WebSocket / SSE）
├── pure/                纯函数（无框架依赖）
└── tools/               通用工具（19 个，自动发现）
spiderlx/               浏览器自动化引擎（CDP/Selenium）
skills/                  Skill 配置中心（Agent 能力定义，YAML 驱动自动发现）
config/settings.py       模型 / JWT / 数据库配置
db/                      MySQL + Redis（云端）
frontend/                React 18 + TypeScript + React Router 前端
├── src/
│   ├── App.tsx               路由主入口（BrowserRouter + AuthProvider + 导航栏）
│   ├── contexts/
│   │   └── AuthContext.tsx   认证上下文
│   ├── pages/
│   │   ├── AgentAnalysisPage.tsx    数据分析全屏页（/agent/analysis）
│   │   ├── AgentAutomationPage.tsx  自动化全屏页（/agent/automation）
│   │   └── AgentKnowledgePage.tsx   知识库全屏页（/agent/knowledge）
│   └── components/
│       ├── ChatPage.tsx           对话界面（群聊式多 Agent 气泡）
│       ├── AdminPage.tsx          后台管理（11 Tab，嵌套路由 /admin/*）
│       ├── LoginPage.tsx          登录页（/login）
│       ├── AgentStatus.tsx        顶部栏 Agent 在线指示灯
│       ├── ToolCallCard.tsx       工具调用卡片（含 Agent 身份标签）
│       └── MarkdownContent.tsx    富文本渲染（表格/代码/图片）
data/                   数据目录
```

## 对话界面

唯一业务入口。欢迎页居中显示输入框，历史对话以群聊形式展示：
- 蓝色 = 小元AI（统筹）
- 紫色 = 数据分析 Agent
- 青色 = 数据采集 Agent
- 橙色 = 自动化 Agent

每个 Agent 气泡上方有彩色标签和身份标识，工具调用卡片显示 Agent 归属。

聊天图片：`data/chat_images/` 文件存储，经公开路由 `/api/v1/chat/image/{sid}/{fname}` 提供（`Cache-Control: immutable`，文件名含 UUID）。前端 `addToken` 对此路由**不拼接 JWT**——拼 token 会在每次登录后改变 URL，击穿浏览器缓存导致历史图片全部重新下载。

## 后台管理

12 个 Tab，每个有独立 URL 路由（`/admin/:tab`）：

| Tab | 路由 | 内容 |
|-----|------|------|
| 仪表盘 | `/admin/dashboard` | 用户数/会话数/消息数/在线Agent + 30天消息量图 |
| 用户管理 | `/admin/users` | 创建/冻结/删除用户 |
| 网站管理 | `/admin/websites` | 添加/删除采集网站 |
| Agent 状态 | `/admin/agents` | 在线状态 + 4 个子 Agent 团队卡片 + 实时活动记录 |
| 会话记录 | `/admin/sessions` | 历史会话查询 |
| 模型配置 | `/admin/models` | 已配置模型列表 |
| 数据集 | `/admin/datasets` | 上传/查看/删除数据集 |
| 知识库 | `/admin/knowledge` | 知识库文档管理 |
| 文件管理 | `/admin/files` | 服务器文件浏览 |
| 工具 | `/admin/tools` | 已注册工具列表 |
| 代码监控 | `/admin/monitor` | Git 轮询 + 代码变更趋势图 + 文件类型分布 + 实时活动日志 |
| 设置 | `/admin/settings` | 系统设置 |

## WebSocket 桥接

- 本地 Agent 主动连接云端 `ws://<server>/api/v1/agent/ws/agent/{agent_id}`
- 云端收到 HTTP 对话请求 → 检查 Agent 在线 → WebSocket 转发 → Agent 处理后回传 → SSE 推送前端
- Agent 离线时自动回退到云端直接调用 LLM

## Claude Code 桥接（Phase 2）

独立桥接进程让云端聊天直接对话本机 Claude Code（流式 token + 工具卡片 + 会话持久化）：

```bash
# 1. 后台管理创建专属用户（如 claude_bridge，role=user）→ POST /admin/agent-token 签发长令牌
# 2. 云端环境变量：CLAUDE_BRIDGE_AGENT_ID=<该用户id> CLAUDE_BRIDGE_ALLOWED_USERNAMES=<白名单用户名>
# 3. 本地启动桥接进程（专属 agent_id + 长令牌）
python -m agent.claude_bridge --server-url wss://cjyuanai.cn --agent-id <用户id> --agent-token <长令牌>
```

- 入口端点：`POST /api/v1/chat/claude-stream`（复用 SSE 桥；离线回退云端 LLM）；前端输入区「⌘ Claude Code」模式切换
- 会话映射：`data/claude_sessions.json`（cloud session_id → claude session uuid，`--resume` 续接；`--session-id` 仅用于新建）
- 事件扩展：`sender_event`（type=agent，声明气泡归属）与 `approval_event`（type=approval，审批卡）
- **审批流未启用**：依赖 claude-agent-sdk 的 `can_use_tool`，当前网络装不了该包（pypi.org 不通、清华源无包）。review 级命令目前靠提示词黑名单约束（同 Phase 1 delegate）
- 验证：`python -m agent.verify_claude_bridge`（离线断言 agent→token→tool→done + 会话续接）

## 工具系统

- 通用工具：`yuanai_core/tools/` 自动发现，39 个（8 个模块，7 个类别：general/crawl/data/file/memory/knowledge/stats）
- 工具类别标签：每个模块顶部 `TOOL_CATEGORY`，`load_tools_for("crawl", "data")` 按需加载
- Agent 专用工具：`agent/tools/` 递归扫描，38 个（浏览器/审核/Cookie/截图）
- 工具总计：39 共享 + 38 专用 = 80 个，按 Agent 角色精准分配
- 分析脚本：9 个，输出协议：`__IMAGES__` + `__HTML__` + `__RESULT__`

### 本地 Claude Code 委派工具

`agent/tools/claude_delegate.py` — 统筹 Agent 的 `delegate_to_claude_agent` 工具：以 `claude -p --output-format stream-json` 子进程在**本机仓库**执行代码/终端/Git 任务，30s `progress` 心跳防 SSE 300s 超时，输出截断 8000 字符。

安全边界（重要）：
- **Claude Code hooks 在 `-p` 无头模式下不触发**（第三方网关模式下实测），**不要**把 hooks 写进 `.claude/settings.json`——它只会作用于交互会话且钩子进程 cwd 不是项目根（相对路径命令会以 exit 2 报错，锁死本仓库所有交互会话的工具调用，需重启会话清除）
- 实际防护 = 进程级白名单（`--allowedTools Read,Glob,Grep,Write,Edit,Bash` + `--disallowedTools WebFetch,WebSearch` + `acceptEdits` + cwd 锁仓库根 + `--max-budget-usd 10`）+ 提示词硬约束（黑名单命令清单，实测模型会拒绝）+ 审计日志 `data/logs/claude_audit.log`
- `agent/bridge_policy.py` 命令分类（allow/deny/review）与 `scripts/hooks/claude_guard.py` 保留，供后续 SDK 桥接（can_use_tool 审批流）复用

### 工具分配（Token 优化）

| Agent | 工具数 | 加载方式 |
|-------|:------:|---------|
| 统筹 | 8-42 | 意图分类器 → 按类别动态加载（`agent/intent_classifier.py`） |
| 数据分析 | 7 builtin | 脚本派发模式（`skills/analysis/skill.yaml`） |
| 数据采集 | 8 builtin | 脚本派发模式（`skills/collection/skill.yaml`） |
| 自动化 | 14-41 | 意图分类器 → 按组动态加载（`agent/tools/__init__.py`） |

### 意图分类器（零成本）

`agent/intent_classifier.py` — 关键词匹配 + LLM 降级，直接命令（如 "200+300"）跳过 LLM 直接执行工具，节省 30-55% token。

## Skill 系统

Agent 能力通过 `skills/` 目录下的 YAML 配置定义，Orchestrator 自动发现并动态生成 delegate 工具。

```
skills/
├── __init__.py              SkillRegistry 注册中心
├── analysis/skill.yaml      数据分析 Skill（提示词、模型、脚本目录）
├── collection/skill.yaml    数据采集 Skill
└── automation/skill.yaml    自动化 Skill
```

每个 `skill.yaml` 包含：名称、描述、模型、运行模式（script_dispatch / react）、系统提示词、脚本目录、内置工具。

**加新能力无需改代码**：新建 `skills/xxx/skill.yaml` + 可选脚本 → 重启 Agent → 自动注册。Orchestrator 遍历 `skill_registry.get_all()` 动态生成 `delegate_to_xxx_agent` 工具，capabilities 从 `skill_registry.names` 自动生成。

## 权限

| 角色  | 聊天 | 后台管理 |
|-------|------|---------|
| admin | ✅   | ✅      |
| user  | ✅   | ❌      |

## 安全须知

- `.env` 已被 gitignore，永不提交
- API Key 从环境变量读取，不在源码硬编码
- URL 爬取有 SSRF 防护（内网地址拦截）
- JWT 鉴权中间件统一验证
- API 全局限流：Redis 优先 + 内存降级（`api/v1/ratelimit.py`）
- 登录限流 5次/60s，通用 API 60次/60s，上传 10次/60s
- Nginx 层安全响应头（CSP/HSTS/X-Frame-Options 等）

## 数据库迁移

使用 Alembic 管理增量迁移（替代原来的原始 ALTER TABLE + try/except）。

```bash
alembic revision --autogenerate -m "描述"   # 自动检测模型变更
alembic upgrade head                          # 应用到最新
alembic downgrade -1                          # 回滚一个版本
# 或使用辅助命令
python -m db.migrations.helper revision -m "描述"
python -m db.migrations.helper upgrade
```

`AgentDatabase._run_alembic_migrations()` 在每次启动时自动调用 `alembic upgrade head`，失败时降级到 `create_all()`。

## 会话总结惯例

每次对话结束时，用表格总结本次修改的内容和对应的 commit，方便回顾。

示例格式：
```markdown
| 提交 | 内容 |
|------|------|
| `abc1234` | 修复了什么 + 改了什么 |
| `def5678` | 新增了什么功能 |
```

## CI/CD

GitHub Actions（`.github/workflows/ci.yml`）：
- 后端：pip install → pytest → 语法检查
- 前端：npm ci → tsc → lint → build
- Docker：构建验证后端镜像 + 前端镜像

`deploy/Dockerfile.backend` 注意：安装 torch 前必须先预装 `Jinja2`/`typing_extensions`（清华源、精确名称、版本与 requirements.txt 一致）——torch 依赖声明的小写/连字符写法会被新版 pip 严格校验判为不一致，丢弃 pytorch 索引 wheel 转 sdist 构建，而该索引不托管 flit_core 导致构建失败。改动这条 RUN 时勿删预装行。

## 数据分析大屏

分析 Agent 采用 ScriptDispatchAgent 模式：LLM 根据用户意图从 `agent/datanalysis/scripts/` 自动选择脚本，通过 subprocess 执行。

**脚本输出协议：**
- `__script_name__` / `__script_tags__` / `__script_params__` — 脚本元数据，ScriptRegistry 自动发现
- `__IMAGES__:path` — 图片输出（脚本 stdout），Registry 转为 base64 嵌入聊天
- `__RESULT__:{json}` — 结构化结果（用于大屏展示），Registry 检测后缓存到文件，通过 `__DASHBOARD__:path` 回传
- 协调器检测 `__DASHBOARD__` → 缓存至 Redis → 大屏页面读取渲染

**大屏页面：**
- `/agent/rfm` — RFM 3D 散点大屏（直连 API，不需要 Agent）
- `/agent/dashboard/:sessionId` — 通用分析大屏（从 Redis 读取 Agent 执行结果，降级到直连 API）
- 聊天中分析 Agent 消息的"打开面板"按钮指向 `/agent/dashboard/{sessionId}`

**分析 API：**
- `POST /api/v1/analysis/rfm` — RFM 分析（支持 dataset_id 或默认示例文件）
- `GET /api/v1/analysis/dashboard/{session_id}` — 读取 Agent 缓存的仪表盘数据
- `GET /api/v1/analysis/rfm-chart/{filename}` — Plotly 3D 图表 HTML（公开路径，iframe 嵌入）

**内置工具（Agent 可直接调用）：**
- `list_datasets` / `preview_dataset` / `analyze_dataset` — 数据集管理
- `transform_dataset` / `describe_column` / `correlate_columns` — 数据转换与分析
