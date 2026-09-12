# 小元AI — 云边协同多智能体平台

## 项目概览

前后端分离的多智能体协作平台，以对话为统一入口，集成数据分析、数据采集、浏览器自动化。Web 运行在云服务器（火山引擎），本地 Agent 负责实际任务执行。统筹 Agent（Orchestrator）自动识别意图并委派专业子 Agent 处理。

## 启动方式

```bash
# 云端 API（端口 8000）
python -m api.main

# React 前端（端口 5173）
cd frontend && npm run dev

# 本地 Agent 首次安装（机器注册，一次性；后台「Agent 管理」签发安装码）
python -m agent.main --install YUAN-XXXX-XXXX-XXXX --server-url ws://localhost:8000

# 本地 Agent 日常启动（自动读 data/agent_identity.json；旧模式 --agent-id 1 仍兼容）
python -m agent.main

# 本地 Agent（托盘模式，发布用；首次启动无身份时弹窗引导输入安装码）
python -m agent.main --tray

# 一键启动（Windows 双击 start_agent.bat）
# 发布版 exe：python -m PyInstaller agent/yuanai_agent.spec（产物 dist/小元AI Agent.exe，
#   上传服务器 downloads/yuanai-agent.exe，后台「Agent 管理」与官网首页提供下载入口）
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
    ├── planet/            知识星球（星球→导图→线性笔记三级知识库；批量导入 jobs 轮询）
    └── ...
agent/                  本地 Agent 运行时 ★
├── main.py              入口（--tray 托盘 / 默认命令行）
├── orchestrator.py      统筹 Agent（动态 delegate 工具，从 skills/ 自动发现）
├── ws_client.py         WebSocket 客户端（自动重连）
├── tray.py              系统托盘程序（pystray；首启安装码弹窗 + Agent 开关菜单 + 二合一 Claude 分支 + 冻结模式 --run-script 脚本执行入口）
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
│   ├── mindmap_parser.py   思维导图多格式解析器（html高保真/mm/xmind/opml/emmx/md→统一树）
└── tools/               通用工具（19 个，自动发现）
spiderlx/               浏览器自动化引擎（CDP/Selenium）
skills/                  Skill 配置中心（Agent 能力定义，YAML 驱动自动发现）
config/settings.py       模型 / JWT / 数据库配置
db/                      MySQL + Redis（云端）
frontend/                React 18 + TypeScript + React Router 前端
├── src/
│   ├── App.tsx               路由主入口（BrowserRouter + AuthProvider + 导航栏；/ 公开官网首页，/chat/* 登录后应用）
│   ├── contexts/
│   │   └── AuthContext.tsx   认证上下文
│   ├── pages/
│   │   ├── AgentAnalysisPage.tsx    数据分析全屏页（/chat/agent/analysis）
│   │   ├── AgentAutomationPage.tsx  自动化全屏页（/chat/agent/automation）
│   │   └── AgentKnowledgePage.tsx   知识库全屏页（/chat/agent/knowledge）
│   └── components/
│       ├── ChatPage.tsx           对话界面（群聊式多 Agent 气泡）
│       ├── icons.tsx              共享 SVG 图标库（lucide 风格 stroke，零图标库）
│       ├── LandingPage.tsx        官网公开首页（免登录，Hero/能力/特性/功能入口区/CTA；功能入口直达 /chat/agent/* 各面板）
│       ├── LandingHeader.tsx      公开页共享 Header（首页/关于我们导航 + 主题 + 登录态按钮）
│       ├── AboutPage.tsx          关于我（个人简历，免登录）
│       ├── MedicalPage.tsx        医学与生命科学工作台（/chat/agent/medical：PubMed检索/物种导航/药物可行性）
│       ├── CollectionRecordsPage.tsx 采集记录页（/chat/agent/records：列表/详情/删除）
│       ├── AdminPage.tsx          后台管理（11 Tab，嵌套路由 /admin/*）
│       ├── LoginPage.tsx          登录页（/login）
│       ├── AgentStatus.tsx        顶部栏 Agent 在线指示灯
│       ├── ToolCallCard.tsx       工具调用卡片（含 Agent 身份标签）
│       └── MarkdownContent.tsx    富文本渲染（表格/代码/图片）
data/                   数据目录
```

## UI 规范（图标优先，按场景审慎适用，不搞一刀切）

- **短文字按钮保留文字**（≤4 字：发送/删除/刷新/搜索/取消/确定等）——短文字本身就是最好的图标，纯图标化会伤体验
- **字符图标/emoji 一律不用**（✕ ▶ ◀ ⚠ ● ○ ↑ ↓ 📎 📊 等字符画），替换为 `frontend/src/components/icons.tsx` 的内联 SVG（lucide 风格 stroke，零图标库）
- **图标 + 文字组合**：原「← 返回」类按钮改为 SVG 箭头 + 「返回」；按钮里混用的 emoji/字符图标换成 SVG 后保留文字
- **纯图标按钮**只用于语义广为人知的操作（上传附件、语音通话、关闭、删除行等），配悬浮提示
- **悬浮提示**：统一 `.yuan-tip`（index.css 定义，`data-tip` 属性，主题色反相气泡随明暗自适应），配 `aria-label`；原生 `title` 仅在父容器 `overflow:hidden`（侧栏/表格内）会裁剪气泡时使用
- **豁免**：标题/正文/表单标签/表格表头/营销文案等内容性文字保留；公开页（官网/登录）文字即内容，谨慎图标化；移动端无悬浮提示，关键 CTA 保留文字

## 对话界面

业务入口。域名根路径 `/` 是**免登录的官网公开首页**（LandingPage，静态内容 + 基础 SEO + 「小元数据冲刺」Canvas 小游戏 `DataRunGame.tsx`，零依赖跑酷，主题跟随明暗），`/about` 是**关于我公开页**（个人简历，匿名署名），两者共享 LandingHeader（首页/关于我们导航）。聊天页在 `/chat`（ProtectedRoute 保护，未登录跳 `/login`，登录后落 `/chat`），Header 按登录态显示「进入对话」/「登录」。聊天欢迎页居中显示输入框，历史对话以群聊形式展示：
- 蓝色 = 小元AI（统筹）
- 棕色/橙色 = Claude Code（本机桥接）
- 紫色 = 数据分析 Agent
- 青色 = 数据采集 Agent
- 橙色 = 自动化 Agent

每个 Agent 气泡上方有彩色标签和身份标识，工具调用卡片显示 Agent 归属。

聊天图片：`data/chat_images/` 文件存储，经公开路由 `/api/v1/chat/image/{sid}/{fname}` 提供（`Cache-Control: immutable`，文件名含 UUID）。前端 `addToken` 对此路由**不拼接 JWT**——拼 token 会在每次登录后改变 URL，击穿浏览器缓存导致历史图片全部重新下载。

消息气泡操作（气泡内部图标行，常显）：用户气泡 = 复制/修改（修改后截断其后所有消息并重发，复用 SSE 发送链路）；AI 气泡 = 复制（**markdown 原文**）/点赞。点赞后端持久化：`ai_chat_feedback` 表（会话内消息下标定位，Alembic 0004 迁移），`POST/GET /api/v1/chat/feedback` 读写，`/chat/save` 全量替换时清理下标越界的孤儿行。图标均为内联 SVG stroke（项目零图标库）。已知限制：Claude 桥接模式修改重发 = 续接对话（claude 会话无法回退）；消息无 id，点赞/修改按数组下标定位；语音转录（/voice/message append）与文字保存（/chat/save 全量替换）两条持久化路径并存无幂等键——根治需消息引入 id（架构债，见审查基线 6c154fd 之后再做）。

## 开发经验教训（2026-09-04 全量代码审查沉淀）

1. **跨文件复制私有 helper 必漏 import**：照抄 `_get_db/_verify_session_owner` 用法却不带定义 → 运行时 NameError，py_compile 查不出。复制后立即 grep 验证每个名字在本模块可解析，或提共享模块。
2. **mount-only useEffect 冻结 props 闭包**：长生命周期 RTC 回调必须走 `propsRef.current = props` 每帧刷新模式（VoiceCall 已示范），否则 loading 守卫失效、会话反复新建。
3. **同一数据实体只允许一条写入路径**：新增写路径前先问幂等键在哪。

## 后台管理

13 个页面，每个有独立 URL 路由（`/chat/admin/:tab`，嵌套在 AppLayout 内）。导航为**左侧边栏按维度分组**（桌面 ≥769px；移动端回退顶部横向滚动 chip），分组结构在 `frontend/src/components/admin/index.tsx` 的 `NAV_GROUPS`：

| 分组 | 页面 | 路由 | 内容 |
|------|------|------|------|
| 概览 | 仪表盘 | `/admin/dashboard` | 用户数/会话数/消息数/在线Agent + 30天消息量图 |
| 用户维度 | 用户管理 | `/admin/users` | 创建/冻结/删除用户 |
| 用户维度 | 会话记录 | `/admin/sessions` | 历史会话查询 |
| Agent 维度 | Agent 状态 | `/admin/agents` | 在线状态 + 子 Agent 团队卡片 + 实时活动记录 |
| Agent 维度 | Agent 管理 | `/admin/agent-devices` | 签发安装码、设备列表、一对一绑定、解绑/冻结 |
| Agent 维度 | 工具 | `/admin/tools` | 已注册工具列表 |
| 数据维度 | 数据集 | `/admin/datasets` | 上传/查看/删除数据集 |
| 数据维度 | 知识库 | `/admin/knowledge` | 知识库文档管理 |
| 数据维度 | 网站管理 | `/admin/websites` | 添加/删除采集网站 |
| 数据维度 | 文件管理 | `/admin/files` | 服务器文件浏览 |
| 系统维度 | 模型配置 | `/admin/models` | 已配置模型列表 |
| 系统维度 | 代码监控 | `/admin/monitor` | Git 轮询 + 代码变更趋势图 + 文件类型分布 + 实时活动日志 |
| 系统维度 | 设置 | `/admin/settings` | 系统设置 |

## WebSocket 桥接

- 本地 Agent 主动连接云端 `ws://<server>/api/v1/agent/ws/agent/{agent_id}`
- 云端收到 HTTP 对话请求 → 检查 Agent 在线 → WebSocket 转发 → Agent 处理后回传 → SSE 推送前端
- Agent 离线时自动回退到云端直接调用 LLM

### 机器识别（每用户一台 PC）

- 安装流程：后台「Agent 管理」签发安装码（`POST /admin/agent-codes`）→ 用户本机 `python -m agent.main --install <安装码>`（或 exe 双击后弹窗粘贴安装码）→ 云端注册设备（`POST /agent/register`，公开路径，安装码即凭证）→ 本机保存 `data/agent_identity.json`（agent_id + agent_secret）
- **Agent 开关**：托盘菜单勾选启用哪些 Agent（数据分析/采集/自动化/生命科学/Claude Code），持久化 `data/agent_config.json`，切换即重连生效；统筹 Agent 按开关过滤委派工具（`Orchestrator(enabled_skills=..., enable_claude=...)`）
- WS 鉴权两种凭据：JWT（旧模式，user_id==agent_id）或 agent_secret（机器模式，查 `agent_devices` 表）
- 路由：`get_agent(user_id)` 先查旧模式直连，再查一对一绑定（`agent_devices.user_id`，30s 缓存）→ 转发到绑定的设备 socket
- 一对一绑定：后台「Agent 管理」页操作（设备↔用户互不重复绑定，可解绑/冻结）
- 本机 Agent 是**二合一进程**：chat_request 带 `mode=claude` 走 Claude Code 桥接分支，否则走统筹 Agent

## Claude Code 桥接（Phase 2）

独立桥接进程让云端聊天直接对话本机 Claude Code（流式 token + 工具卡片 + 会话持久化）：

```bash
# 1. 后台管理创建专属用户（如 claude_bridge，role=user）→ POST /admin/agent-token 签发长令牌
# 2. 云端环境变量：CLAUDE_BRIDGE_AGENT_ID=<该用户id> CLAUDE_BRIDGE_ALLOWED_USERNAMES=<白名单用户名>
# 3. 本地启动桥接进程（专属 agent_id + 长令牌）
python -m agent.claude_bridge --server-url wss://cjyuanai.cn --agent-id <用户id> --agent-token <长令牌>
```

- 入口端点：`POST /api/v1/chat/claude-stream`（复用 SSE 桥；离线回退云端 LLM）；前端输入区/欢迎页三模式选择器「云端 / 本地 Agent / ⌘ Claude Code」（离线置灰，在线状态轮询 `/admin/agent-status`，白名单用户可见桥接状态）
- 会话映射：`data/claude_sessions.json`（cloud session_id → claude session uuid，`--resume` 续接；`--session-id` 仅用于新建）
- 事件扩展：`sender_event`（type=agent，声明气泡归属）与 `approval_event`（type=approval，审批卡）
- **审批流未启用**：依赖 claude-agent-sdk 的 `can_use_tool`，当前网络装不了该包（pypi.org 不通、清华源无包）。review 级命令目前靠提示词黑名单约束（同 Phase 1 delegate）
- 验证：`python -m agent.verify_claude_bridge`（离线断言 agent→token→tool→done + 会话续接）

## 语音对话

火山引擎「AI 音视频互动方案」实时语音（豆包 App 同款：RTC + 豆包 ASR/TTS + 方舟 LLM）：

- 流程：输入区 🎙️ 按钮 → `POST /api/v1/voice/start`（创建 room/task → StartVoiceChat 启动 AI 智能体入房 → 签发 RTC Token）→ 前端 `@volcengine/rtc` SDK joinRoom + 麦克风采集 → 挂断 `POST /api/v1/voice/end`（StopVoiceChat）
- 后端纯 Python 零新依赖：`api/v1/voice/rtc_token.py`（VeRTC Token「001」新版二进制格式，密钥 AppKey）、`v4_sign.py`（OpenAPI V4 签名，域 rtc.volcengineapi.com，Version=2024-12-01）
- 请求体已对齐官方 rtc-server-demo-open 1201 大模型模板（ASR 直接字段 + ApiResourceId=并发版；TTS 走 volcano_bidirection + volc.service_type.10029）；联调参数集中在 `_build_start_body()`
- 前端 `VoiceCall.tsx` 悬浮通话卡（桌面居中 / 手机全屏）：音量波形、通话计时、机器人状态/字幕实时展示（subv/conv 协议）、转录落聊天会话；SDK 动态 import 分包（约 2MB，点击才加载）
- 配置：`.env` 的 VOLCANO_ACCESS_KEY/SECRET_KEY（IAM）、VOLCANO_RTC_APP_ID/APP_KEY（RTC 应用）、VOICE_LLM_ENDPOINT_ID（方舟接入点）、VOICE_ASR/TTS_APP_ID+ACCESS_TOKEN（豆包语音控制台）、VOICE_ASR_RESOURCE_ID（须并发版）、VOICE_TTS_VOICE_BOT（通话机器人音色，主智能体=少年梓辛小男孩）；未配置时 /voice/start 返回 503
- **气泡朗读（豆包同款）**：AI 消息喇叭图标 → `POST /api/v1/voice/tts`（seed-tts-2.0 单向流式，响应为换行分隔 JSON 流 + base64 mp3）→ 浏览器播放，播放中波形动画可打断
- **每 Agent 独立音色**：`config/settings.py` 的 `AGENT_VOICE_MAP`（6 键：orchestrator/local/analysis/collection/automation/claude，默认小元=少年梓辛）；用户设置页（/chat/settings）「语音音色」卡经 `GET/PUT /api/v1/auth/agent-voices` 改 models.json 的 `_agent_voices` 键；`voice_tts` 按消息 sender 查表选音色。**音色须为 2.0 uranus 系列**（1.0 mars 会 55000000 不匹配），预置 12 个音色全部本地实测有效

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

## 成本护栏（2026-09-11）

- 注册默认关闭：`REGISTER_OPEN`（.env，默认 false；用户由管理员后台创建，或开关打开后走 /auth/register 恢复注册逻辑）
- 每日消息配额：`DAILY_MESSAGE_QUOTA`（默认 50 条/用户/天，admin 不限；/chat/stream 入口 Redis 计数 `quota:msg:{uid}:{date}`，Redis 故障降级放行）
- 语音总开关：`VOICE_ENABLED`（voice/start 与 voice/tts 检查，关闭返回 503）
- 网站访问统计：`visit_log` 表（Alembic 0005）+ 公开 `POST /api/v1/stats/visit`（前端 LandingPage/AboutPage 埋点，全局限流保护）+ 后台仪表盘 PV/UV/7 天趋势

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
- `__PROGRESS__:{json}` — 脚本进度（可选，`{"current","total","message"}`）；registry 同时有 10s 时间心跳（存量脚本零改动也有进度）
- 协调器检测 `__DASHBOARD__` → 缓存 Redis（TTL 1h）**并落库 analysis_history** → yield dashboard_event

**大屏页面：**
- `/agent/rfm` — RFM 3D 散点大屏（直连 API，不需要 Agent）
- `/agent/dashboard/:sessionId` — **通用分析大屏**：任意 __RESULT__ JSON → KPI 卡/表格/段落/嵌套分组（已知键位中文适配，`frontend/src/pages/AnalysisDashboard.tsx` 的 KEY_LABELS）；plotly 图表走 iframe
- 聊天中「打开面板」按钮由 **dashboard SSE 事件**触发挂载（数据就绪才出现，非 tool_start 预挂）
- Redis 过期后 `GET /analysis/dashboard/{sid}` 从 analysis_history 恢复（带 recovered/created_at），数据不再 1 小时蒸发

**分析 API：**
- `POST /api/v1/analysis/rfm` — RFM 分析（支持 dataset_id 或默认示例文件）
- `GET /api/v1/analysis/dashboard/{session_id}` — 大屏数据（Redis → analysis_history 降级）
- `GET /api/v1/analysis/history?session_id=` — 大屏历史列表
- `GET /api/v1/analysis/rfm-chart/{filename}` — Plotly 3D 图表 HTML（公开路径，iframe 嵌入）
- iframe 鉴权：`/api/v1/data/script-html`、`/api/v1/data/analysis-html` 支持 `?token=`（middleware `_extract_token`）

**医学 API（`api/v1/medical/router.py`，JWT 保护）：**
- `GET /api/v1/medical/species` — 物种→MeSH 导航列表
- `GET /api/v1/medical/search?q=&max=` — PubMed 文献检索（esearch+efetch，NCBI 失败返回 502）
- `POST /api/v1/medical/feasibility` — 药物可行性评估（LLM，verdict 高/中/低 + 理由 + 置信度）

**内置工具（Agent 可直接调用）：**
- `list_datasets` / `preview_dataset` / `analyze_dataset` — 数据集管理
- `transform_dataset` / `describe_column` / `correlate_columns` — 数据转换与分析
