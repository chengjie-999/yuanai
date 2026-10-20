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
# 安装包化（2026-10-16）：exe 双击自动引导安装（选目录/桌面快捷方式/旧数据迁移），
# 数据统一落 %LOCALAPPDATA%\XiaoYuanAI\data，不再散落 exe 所在目录（桌面）
python -m agent.main --tray

# 一键启动（Windows 双击 start_agent.bat）
# 发布版 exe：python -m PyInstaller agent/yuanai_agent.spec（产物 dist/小元AI Agent.exe，
#   上传服务器 downloads/yuanai-agent.exe，后台「Agent 管理」与官网首页提供下载入口；
#   上传端点流式计算 sha256 进 version.json，客户端自动更新强制 https + sha256 校验（缺 hash 拒更），
#   发布顺序：先后端（含 hash）→ 再推新 exe）
```

## 智能体架构（2026-10-14 融合重构：脚本工具直调，对齐业界）

```
用户 → Web 对话界面 → SSE → FastAPI → WebSocket → 本地 Agent
                                                        │
                                              统筹 Agent（意图路由 + function calling）
                                              ┌──────┼──────────┐
                                         脚本工具直调   自动化 Agent   Claude Code
                                        （分析/采集/医学）
```

**执行体分配：**

| 执行体 | 模型 | 职责 |
|-------|------|------|
| 统筹 | doubao-seed-2-0-lite | 意图识别 → 直接调脚本工具（`script_*`，一次调用出结果） |
| 脚本工具 | 由统筹模型带 tools 调用 | 9 个分析脚本 + 通用网页采集 + 医学工具（registry 自动生成 schema，执行经 registry.run 统一校验咽喉） |
| 自动化 | doubao-seed-2-0-pro | 唯一独立子 Agent（react 多步自主）：浏览器控制、题目审核、截图监控 |
| Claude Code | 本机 | 桥接：代码、终端、Git |

**脚本工具 key 对照**（`agent/scripts/registry.py SCRIPT_KEYS` 静态表，未登记 md5 兜底）：descriptive_stats/correlation/regression/categorical/timeseries/preprocess/rfm_cluster/churn_predict/gene_expression/generic_crawl。

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
    ├── monitor/           代码进度实时监控（Git 轮询 + 可视化仪表盘 + 架构图/ER 图实时生成）
    ├── planet/            知识星球（星球→导图→线性笔记三级知识库；批量导入 jobs 轮询）
    └── ...
agent/                  本地 Agent 运行时 ★
├── main.py              入口（--tray 托盘 / 默认命令行）
├── orchestrator.py      统筹 Agent（脚本工具直调 + automation 唯一 delegate）
├── ws_client.py         WebSocket 客户端（自动重连）
├── tray.py              系统托盘程序（pystray；首启安装码弹窗 + Agent 开关菜单 + 二合一 Claude 分支 + 冻结模式 --run-script 脚本执行入口）
├── verify.py            多智能体链路验证脚本
├── yuanai_agent.spec    PyInstaller 打包规格
├── agents/              子 Agent（融合后仅 automation）
│   └── automation.py    自动化子 Agent（react）
├── scripts/             脚本注册表 + 工具工厂
│   ├── registry.py      ScriptRegistry（参数校验/执行咽喉/SCRIPT_KEYS）
│   └── tools.py         脚本工具工厂（每脚本 → StructuredTool）
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
│       ├── ApiDocsPage.tsx        API 文档页（/api-docs，免登录；README.md 实时同步渲染 + API 示例条目）
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
- **面板入口规范（2026-10-17 用户拍板，对话中生成的面板统一此形态）**：计划/分析看板/自动化等子页面入口 = **合并框**——左侧彩色「打开面板」按钮 + 右侧明文链接（monospace，点击复制完整 URL，可直接浏览器打开）；子页面窗口（桌面浮窗可拖动+右下角缩放 / 移动全屏浮层 / 浏览器独立路由）三形态布局统一：标题栏只留「返回对话」+ 浏览器式明文地址栏（点击复制）。新增面板入口一律复用 MessageBubble 的 pageLink 合并框渲染

## 配色与设计规范（2026-10-18 用户拍板：全前端统一，应用界面不搞首页式花哨）

**分层原则**：营销页（LandingPage/登录页）可以花哨——渐变标题、神经元背景、光晕球、玻璃拟态、入场动画；**应用界面（聊天/后台/各面板/设置）一律克制**——纯色分层 + 微交互，不做渐变铺底、不做装饰动画。

**色板（全部经 `frontend/src/index.css` CSS 变量消费，新增颜色先加变量，禁止硬编码 hex）**：

| 变量 | 亮色 | 暗色 | 用途 |
|------|------|------|------|
| `--bg-primary` | #f8fafc | #0b1220 | 页面底 |
| `--bg-secondary` | #f1f5f9 | #101a2c | 侧栏/分区底 |
| `--bg-tertiary` | #e2e8f0 | #16233a | 代码块/输入框底/chip |
| `--bg-input` | #ffffff | #1b2942 | 输入框 |
| `--text-primary` | #0f172a | #e2e8f0 | 标题/正文 |
| `--text-secondary` | #475569 | #94a3b8 | 次要说明 |
| `--text-muted` | #64748b | #64748b | 占位/弱化信息 |
| `--border` / `--border-light` | #cbd5e1 / #e2e8f0 | #2b3b56 / #1f2c44 | 描边两级 |
| `--accent` / `--accent-light` | #2563eb / rgba(37,99,235,.09) | #60a5fa / rgba(96,165,250,.13) | 品牌蓝/淡底 |
| `--accent-soft` / `--accent-glow` | rgba(59,130,246,.12) / .35 | rgba(96,165,250,.14) / .30 | 强调淡底/光晕 |
| `--accent-gradient` | 135deg #3b82f6→#2563eb→#1d4ed8 | 135deg 浅蓝渐变 | 仅品牌强调点（CTA/统计数字/装饰线） |
| `--danger` / `--success` / `--warning` | #dc2626 / #16a34a / #d97706 | #f87171 / #4ade80 / #fbbf24 | 语义色 |
| `--danger-soft` / `--success-soft` / `--warning-soft` | 各语义色 10-14% 淡底 | 同左（随语义色换调） | 状态徽章底/错误横幅底 |
| `--header-bg` | #ffffff 实底 | rgba(16,26,44,.86) | 顶栏（亮色不半透明） |
| `--shadow-sm` / `--shadow-md` | rgba(15,23,42,.05) / .10 | rgba(0,0,0,.30) / .50 | 阴影两级 |

**组件规则**：
- **文字层级三档**：primary（标题正文）/ secondary（说明）/ muted（占位弱化），小字禁用更浅的灰
- **按钮**：primary=accent、danger/success=语义变量、warning=#f59e0b 深字、outline=白底 border 描边 text-primary；**暗色模式按钮底必须换深色调**（暗色 accent/danger/success 变量是浅色作文字用的，白字对比不足——index.css 已有 dark 覆盖，新增按钮照此写）；inline 样式做不了主题分支的实底按钮加 `.bg-success-solid`（已含暗色深调覆盖）
- **状态徽章/文字**：语义色一律 `var(--success/warning/danger)`（作文字色时暗色浅调正合适）；淡底用 `*-soft` 变量；admin `badge()` 助手已改 color-mix 支持传 var——**不要传硬编码 hex**
- **卡片**：亮色=白底 `#fff` + `--border-light` 描边 + `--shadow-sm`；暗色=`--bg-secondary` + `--border`；glass backdrop-filter 仅营销页
- **圆角**：小元素（按钮/输入框）6px，卡片 12–14px，chip 999px
- **动效**：应用内微交互 0.12–0.18s（hover/active）；大块入场动画（fade-up/float）仅营销页；尊重 `prefers-reduced-motion`
- **渐变只出现在**：主 CTA 按钮、统计数字文字、标题装饰线、营销页 Hero——不铺满应用界面
- **主题切换**：一切颜色经变量自适应；Canvas 类组件（NeuralBackground 等）用 MutationObserver 监听 `data-theme` 换调色板
- **豁免清单（2026-10-18 一致性清扫边界，新增色先对照本表）**：① 图表系列色板（recharts 多序列需多色区分，Dashboard/Analytics/Monitor/UserAnalytics 的 CHART_* 常量）② Agent/服务商身份色（agents.ts 各智能体识别色、ToolCallCard AGENT_LABELS、ModelSelector 服务商色）③ 吉祥物画作（Mascot）④ 营销公开页（Landing/Login/About 自含花哨样式）⑤ index.css 变量定义与暗色按钮深调覆盖本身

## 对话界面

业务入口。域名根路径 `/` 是**免登录的官网公开首页**（LandingPage，静态内容 + 基础 SEO + 神经元网络 Hero 背景 `NeuralBackground.tsx`，零依赖 Canvas，主题跟随明暗），`/about` 是**关于我公开页**（个人简历，匿名署名），两者共享 LandingHeader（首页/关于我们导航）。聊天页在 `/chat`（ProtectedRoute 保护，未登录跳 `/login`，登录后落 `/chat`），Header 按登录态显示「进入对话」/「登录」。聊天欢迎页居中显示输入框，历史对话以群聊形式展示：
- 蓝色 = 小元AI（统筹）
- 棕色/橙色 = Claude Code（本机桥接）
- 紫色 = 数据分析 Agent
- 青色 = 数据采集 Agent
- 橙色 = 自动化 Agent

每个 Agent 气泡上方有彩色标签和身份标识，工具调用卡片显示 Agent 归属。

**思考/工具/回答时序交叉渲染（2026-10-19）**：模型输出顺序 = 思考→工具调用→思考→…→最终思考→正式回答。气泡内不再把思考堆顶部——每段思考快照到其触发的工具卡上方（tool_start 时取累积 reasoning 并复位重计），首个 token 时剩余思考存为「最终思考」（`finalReasoning`，META 短键 fr）置于回答上方；旧消息整段 reasoning（META.r）兼容渲染在折叠区顶部。折叠区标题「思考 (Xs) · N 次工具调用」，流式期间展开、完成后默认收起（用户手动了则不干预）。

**@指定智能体（群聊式定向）**：输入区 @ 按钮（或输入 `@`）弹出选择面板（**统筹/自动化/Claude**，融合后分析/采集并入统筹不再单独指定），选定后本条消息确定性分派。分派链路：`target_agent` 字段贯穿 ChatRequest（云端 models/schemas → chat/router → ws_client）→ Agent 端 `agent/main.py` + `agent/tray.py` 的 `route()` 三路分派（mode=claude 桥接 / target=automation → `Orchestrator.stream_target()` 直接调 automation Agent / 其余统筹）。`stream_target` 与 delegate 工具共用 `_extract_tool_output`（图片/大屏/HTML 协议提取）。**群聊规则（微信式群聊定位）**：本地 Agent 离线时子智能体在 @ 面板置灰不可选（不做云端角色冒充），@Claude Code 需桥接在线；离线降级 role_hint（仅 API 直调时）强制身份不自称小元AI。

**群聊说话人协议（信封化，2026-10-11 升级）**：身份从「正文【xx】前缀靠模型写」升级为**信封元数据**（sender/recipient/turn/type，编排代码填，模型碰不到）+ **视图滤波**（每个 Agent 只看自己该看的部分）。核心：`yuanai_core/core/message.py`（Envelope 编解码，短键 s/rp/tn/ty，与前端 encodeMsg/parseHistory 对偶）+ `yuanai_core/core/views.py`（`view_for(agent, messages, self_senders, envelopes)` 七规则滤波 + `compose_target_prompt`）。信封过云端的载体 = ChatRequest **并行数组 `envelopes`**（build_input_messages 会重建 dict 丢附加键）；落库 ai_chat 四列（迁移 0014 + 自包含 backfill：user→'user'、assistant→META.s 或 orchestrator）；读取优先级 列 > META > 缺省；全空信封退化直通（旧数据兼容）。裁剪点四处：云端 /stream 与 claude-stream 回退分支、本地 Orchestrator.stream、stream_target/delegate_fn。tool_start/tool_end 事件带 sender（前端 senderFromTool 降级为兜底）。

**置顶主对话（豆包式）**：`chat_session.is_main`（迁移 0013）每用户一条，`ensure_main_session()` 幂等取/建，`POST /api/v1/chat/main-session`；侧栏图钉置顶显示；**登录直接落主对话**（挂载时 ensure + setCurrentSid + parseHistory，欢迎页仅接口异常兜底）；「新对话」按钮=另开普通会话。主对话历史截断最近 **60 条**（chat/router.py `/stream` 主链路，前置「更早的对话已整理进长期记忆」HumanMessage）——与记忆机制配套（二期挂账的 history 截断在此落地）；claude-stream 不截断。欢迎页退场后：推荐问题卡移到对话空状态（ChatView SUGGESTIONS 前 5 条，手机横滑一行）、数据集上传并入输入区回形针（csv/xlsx/xls/json → uploadDataset → `[数据集 #id]` 注入输入框）。输入区布局：textarea 行只留输入框+发送，功能键全部下沉工具行（左动作群 @/图片/语音/朗读/下载，右设置群 模式/推理强度，小屏藏下载）。**AI 会话标题（2026-10-16 修复）**：前端仅新会话首次发送传 title（sendMessages 只透传显式 title）；后端 /chat/save 仅当现标题是自动标题才覆盖（`_is_auto_title` 兼容前端 50 字与后端 80 字两种截断口径）；AI 生成标题（title_gen 豆包 lite 异步）不再被下一条消息压掉。

**滚动跟随（2026-10-12）**：聊天自动跟随最新消息——贴底才跟随（流式直接设 `scrollTop`，无平滑动画防逐 token 抖动）；发送/修改重发/切换会话**无条件滚底并恢复跟随**（`sendTick` 计数从 ChatPage 传入，不看当前位置判定）；上滑阅读历史时**暂停跟随**，同时浮出「回到底部」圆形按钮（`ChatView.tsx` sticky 钉可视区底部居中，yuan-tip 提示 + aria-label，点击平滑滚底恢复跟随）；贴底状态由 scroll 监听实时维护（`nearBottomRef` + `showJump`）。

聊天图片：`data/chat_images/` 文件存储，经公开路由 `/api/v1/chat/image/{sid}/{fname}` 提供（`Cache-Control: immutable`，文件名含 UUID）。前端 `addToken` 对此路由**不拼接 JWT**——拼 token 会在每次登录后改变 URL，击穿浏览器缓存导致历史图片全部重新下载。

消息气泡操作（气泡内部图标行，常显）：用户气泡 = 复制/修改（修改后截断其后所有消息并重发，复用 SSE 发送链路）；AI 气泡 = 复制（**markdown 原文**）/点赞/点踩/**重新生成**（点踩后；截断本条及后续 → 重发它前面最后一条用户消息，同修改重发链路；`handleRegenerate` 同步清理被截断消息的反馈态）。点赞后端持久化：`ai_chat_feedback` 表（会话内消息下标定位，Alembic 0004 迁移），`POST/GET /api/v1/chat/feedback` 读写，`/chat/save` 全量替换时清理下标越界的孤儿行。图标均为内联 SVG stroke（项目零图标库）。已知限制：Claude 桥接模式修改重发/重新生成 = 续接对话（claude 会话无法回退）；消息无 id，点赞/修改按数组下标定位；语音转录（/voice/message append）与文字保存（/chat/save 全量替换）两条持久化路径并存无幂等键——根治需消息引入 id（架构债，见审查基线 6c154fd 之后再做）。

## 娱乐模式（双模式产品，E1 基建 2026-10-21）

- **双模式**：工作模式=现状（云+本地 Agent：数据分析/计划/自动化）；娱乐模式=**纯云端智能体**（不走本地 Agent），C 端陪伴式对话。入口：输入区工具行右侧「工作/娱乐」分段开关（localStorage `entertainmentMode` 持久化）。
- **协议**：ChatRequest 新增 `chat_mode: "work" | "entertainment"`（api/v1/models.py；frontend streamChat 透传）；云端 /stream 里 entertainment 强制跳过 Agent 桥接、忽略 @定向（不委派、hist_limit 不因 target 放宽）、专属娱乐人设提示 `_ENTERTAINMENT_SYSTEM_PROMPT` + 身份卡 `docs/agents/entertainment.md`（agent_docs 加载，单一事实源，改文档即改人设）。
- **前端联动**：娱乐模式下 @ 按钮隐藏、聊天模式强制 cloud（退出恢复原模式，prevChatModeRef）、欢迎页模式下拉替换为「娱乐模式 · 云端直达」徽章；发送链路（sendMessages/sendWithNewSession）entMode 时忽略 target/dmTarget、isClaude 恒 false、placeholderSender=orchestrator。
- **记忆复用**：娱乐对话走同一 /chat/save 落库 → 折叠 worker 同样沉淀记忆；system 注入与云端直连分支同一段代码。
- **路线图**（plans/entertainment-mode-2026-10.md）：E2 火山生图（**执行前确认方舟账号开通与模型**）→ E3 生视频（异步任务制）→ E4 搜索联动 → E5 C 端打磨。限额护栏必须与生图/生视频工具同日上线，不允许裸奔。
- **验证**：test/test_entertainment_mode.py（娱乐跳过桥接+人设生效+@定向忽略 / 工作模式对照）；真机 SSE 双模式均实测通过。conftest 登录密码改 test1234（批次3 起密码最少 8 位，test123 只有 7 位导致所有鉴权测试静默跳过）。

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
| Agent 维度 | Agent 状态 | `/admin/agents` | 在线状态 + 能力矩阵卡片 + 实时活动记录 |
| Agent 维度 | Agent 管理 | `/admin/agent-devices` | 签发安装码、设备列表、一对一绑定、解绑/冻结 |
| Agent 维度 | 工具 | `/admin/tools` | 已注册工具列表 |
| 数据维度 | 数据集 | `/admin/datasets` | 上传/查看/删除数据集 |
| 数据维度 | 知识库 | `/admin/knowledge` | 知识库文档管理 |
| 数据维度 | 网站管理 | `/admin/websites` | 添加/删除采集网站 |
| 数据维度 | 文件管理 | `/admin/files` | 服务器文件浏览 |
| 系统维度 | 模型配置 | `/admin/models` | 已配置模型列表 + **Agent 模型分配**（模型淘汰可更换：加新模型 → 切分配 → 删旧模型，全程页面操作热更新） |
| 系统维度 | 代码监控 | `/admin/monitor` | Git 轮询 + 代码变更趋势图 + 文件类型分布 + 实时活动日志 |
| 系统维度 | 设置 | `/admin/settings` | 系统设置 |

**模型淘汰可更换（2026-10-16）**：后台「模型配置」页分三张卡——① 模型清单（添加新模型+API Key 加密存储 / 删除；`get_llm` 前缀匹配 deepseek-*/doubao-* 自动走对应通道）② **Agent 模型分配**（7 键：5 执行体 + memory_fold/planet_article 辅助任务，下拉切换存 models.json `_agent_models`，`PUT /admin/agent-models` 热更新 `settings.reload_agent_models()` 无需重启）③ **语音配置**（tts_model/气泡音色/通话机器人音色/ASR 资源/TTS 资源，`PUT /admin/voice-config` 热更新 `reload_voice_config()`；voice router 的 X-Api-Resource-Id 用 `VOICE_TTS_MODEL`）。删除保护：被分配引用的模型 400 拒绝删除。选择链：**env 优先 → 分配表/语音配置 → 代码默认**；用户侧设置页分配接口（/auth/agent-models）只暴露 5 个执行体（`AGENT_ROLE_KEYS`）。测试 test/test_agent_models_api.py 10 项。

**模型自动检查更新（2026-10-16，确认后自动添加和更换）**：升级知识表 `yuanai_core/pure/model_upgrades.py`（MODEL_UPGRADES 旧→新映射 / UPSTREAM_MODELS 上游清单 / VOICE_UPGRADES 语音模型）由 AI 维护——模型换代时改这一处登记。后台「自动检查更新」卡：`GET /admin/models/upgrade-plan` 对照知识表出升级清单（在用旧模型/语音升级/可添加新模型）→ 管理员点「确认自动更换」→ `POST /admin/models/upgrade` 自动执行（加新模型 + 切分配固化 `_agent_models` + 移旧登记 + 热更新 + 审计 `data/logs/model_upgrade.log`）。`get_llm` 对退役 ID 静默路由到新 ID（存量配置/历史数据不报错）。**2026-10-16 换代**：豆包 2.0→2.1（`doubao-seed-2-0-pro-260628`/`doubao-seed-2-0-lite-260915`）、DeepSeek V4 Flash→V4.1（新 ID `deepseek-flash`，v4-pro 保留）；语音合成 seed-tts-2.0 仍为官方最新（可配置待换）。

## WebSocket 桥接

- 本地 Agent 主动连接云端 `ws://<server>/api/v1/agent/ws/agent/{agent_id}`
- 云端收到 HTTP 对话请求 → 检查 Agent 在线 → WebSocket 转发 → Agent 处理后回传 → SSE 推送前端
- Agent 离线时自动回退到云端直接调用 LLM（**2026-10-12 加固**：云端回退系统提示整段重写去委派化 `_OFFLINE_SYSTEM_PROMPT`——前端原提示含 delegate 工具清单，那些工具只存在于本地 Agent 进程，云端回退里模型会反复发起不存在的工具调用；同名工具单轮调用 ≤3 次 `limited_tools`（yuanai_core/core/chat.py，包一层计数超限返回引导语）+ LangGraph `recursion_limit` 轮数上限，双层防重复调用死循环）

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

- 入口端点：`POST /api/v1/chat/claude-stream`（复用 SSE 桥；离线回退云端 LLM）；**微信式群聊下模式下拉已移除**——@Claude Code 即原 ⌘ 桥接模式（前端 sendMessages 里 `isClaude = target==='claude'` 走 claude-stream + 会话续接语义），chatMode 内部自动切换（本地离线 → cloud 标签），ChatModeSelector 组件仅欢迎页兜底保留；手机端顶部栏显示本地 Agent 在线状态（能力清单小屏隐藏），@ 面板内每个智能体标在线/离线
- 会话映射：`data/claude_sessions.json`（cloud session_id → claude session uuid，`--resume` 续接；`--session-id` 仅用于新建）
- 事件扩展：`sender_event`（type=agent，声明气泡归属）与 `approval_event`（type=approval，审批卡）
- **审批流未启用**：依赖 claude-agent-sdk 的 `can_use_tool`，当前网络装不了该包（pypi.org 不通、清华源无包）。review 级命令目前靠提示词黑名单约束（同 Phase 1 delegate）
- **全能力差距路线（2026-10-16 定稿，见 plans/goofy-inventing-turtle.md）**：P0 审批流自建——anthropic SDK 直连自建 agent loop 替换 `claude -p` 子进程（工具面照搬 bridge_policy 白名单；deny/review → approval_event → 前端 ApprovalCard/decision 审批，超时默认 deny fail-closed；只补 can_use_tool 缺口不复刻全功能）；P1 Bash 白名单→审核制；P2 MCP 客户端；P3 会话续接强化。联网被禁维持现状（search_web+fetch_url 替代）
- **CC 桥接搜索通道（2026-10-19）**：白名单 `Bash(python -m:*)` 内提供 `python -m yuanai_core.pure.cc_search "查询" [条数]`——封装平台三级搜索（DeepSeek 官方→Bing→DDG），CC 实时搜索的唯一允许方式；桥接提示词已写明该通道 + 被禁途径（WebSearch/WebFetch/curl/直接跑脚本文件），避免 CC 多轮撞权限墙。更深度检索引导用户走小元AI对话的联网搜索
- **P0 已完成（2026-10-16，`agent/claude_loop.py` + claude_bridge `--sdk` 开关）**：anthropic 1.15 已可安装（此前装不上的是 claude-agent-sdk）；`run_sdk_loop` 流式循环（claude-opus-4-8 默认、adaptive thinking + display summarized、流式 64K 输出）、内置工具声明（bash_20250124 / text_editor_20250728 schema-less + 自定义 Read/Write/Glob/Grep）、执行器（classify allow/deny/review 安全分类 + 仓库内路径校验 + 120s 超时）、审批流（review → approval_event → 前端 ApprovalCard/decision 回传 → approve/deny，超时默认 deny fail-closed）；测试 test_claude_loop.py 11 项全过
- **SDK 模式 auto 化 + DeepSeek 网关适配（2026-10-19 实测）**：sdk_mode 三态——`--sdk` 强制开 / `--no-sdk` 强制关 / **默认 auto（有 Anthropic 凭证即 SDK，无凭证自动降级 CLI）**；`CLAUDE_BRIDGE_MODEL` 换模型（如 deepseek-flash）、`CLAUDE_BRIDGE_THINKING=0` 关 thinking 参数（第三方网关不识别该字段会 400）；`start_bridge.bat` 一键启动（自动读 agent_identity.json 身份）。**国内可行链路已探针验证**：DeepSeek 官方 anthropic 兼容端点（api.deepseek.com/anthropic）流式 + 工具调用 + 网关自带 thinking 全通——数据链路与 Claude Code 同网关一致，合规面零新增；合规底线不变：默认不直连 Anthropic 官方（国内不可用），凭证指向自有/官方兼容网关时 auto 生效
- **智能体能力边界身份卡（2026-10-19，仿 CLAUDE.md 给智能体阅读）**：`docs/agents/*.md`（orchestrator/automation/claude_code/cloud_fallback）为每个智能体定义「你是谁/能做什么/不能做什么/工作方式」，单一事实源改文档即改智能体自我认知；`yuanai_core/agent_docs.py` 加载器（frozen 从 _MEIPASS 读，spec datas 已带 docs/agents/），注入点四处：统筹 stream 追加 system、AutomationAgent 构造、CC 桥接 _BRIDGE_SYSTEM_PROMPT（CLI/SDK 共用）、云端回退 _OFFLINE_SYSTEM_PROMPT。**README 与 /api-docs 同一文件**（`/api/v1/docs/readme` 每次请求读 README.md + `/docs/asset/` 图片资产端点，改 README 即改页面，图片点击放大）
- **长任务小窗（2026-10-16）**：@面板 Claude/自动化行「小窗」按钮 → 新建独立会话持久定向该智能体（dmTargets localStorage），不占主对话截断（@Claude 走 claude-stream 天然不截断；@自动化 后端截断放宽 200 条）；automation 加 10s 心跳进度（聊天气泡进度条可见）；主对话截断提示附各说话人归档计数
- 验证：`python -m agent.verify_claude_bridge`（离线断言 agent→token→tool→done + 会话续接）

## 知识星球（三级知识库）

用户个人知识库：**知识星球（主题域）→ 思维导图 → 线性笔记 markdown**，页面 `/chat/planet`（登录后，按用户隔离）。

- **导入**：整个文件夹拖入（万兴脑图导出），同 stem 自动择优（html 高保真 > md > xmind > mm > opml > emmx 纯文本 > txt），自动归星（文件夹名=星球名）；解析器 `yuanai_core/pure/mindmap_parser.py`（html 的 ed:parentid 完整层级 / emmx 明文文本兜底）
- **AI 文章化**：`yuanai_core/planet_convert.py` 把导图树重写为线性文章（分箱 6000 字、3 箱并行、硬超时 120s、失败落大纲兜底）；模型 `PLANET_ARTICLE_MODEL`（默认豆包 lite，DeepSeek 本地直连实测不稳）；jobs 表 + 1.5s 轮询
- **导图视图**：html 来源直接 iframe 渲染**原始文件**（自包含交互页）；非 html 回退手绘 SVG 树 + 大纲视图
- **检索只读**：`retrieve_planet_knowledge` 工具（聊天可查，气泡挂「知识星球」标签 + 打开面板）；Milvus source=`planet:{uid}:{pid}:{mid}[:note]`；文件 `data/planet/{uid}/{pid}/{mid}/`（**不复用 data/aiprompt**——全量重建会以共享身份索引私人笔记）
- **表**：planets / planet_maps / planet_notes（内容 MEDIUMTEXT）/ planet_jobs（Alembic 0007）
- **视觉**：Canvas 星野背景（Starfield.tsx）+ 天体图标（银河=星球、恒星=导图、行星/卫星=笔记）
- **架构图/ER 图**：`api/v1/monitor/diagrams.py` 请求时实时生成（ER 图 ast 解析 db/session.py）；端点 `/monitor/arch-diagram`、`/er-diagram`（admin）；后台「代码监控」页卡片 + README 嵌入（`python scripts/gen_diagrams.py` 刷新）

## Obsidian vault 双向同步（2026-09-25 落地）

知识星球笔记 ↔ Obsidian vault 指定目录（`知识星球/`）双向同步，本地 Agent 作桥（托盘菜单「vault 同步」勾选 + 「设置 vault 路径...」选目录，配置存 `data/agent_config.json` 的 vault 节；CLI 模式 `python -m agent.main --vault-sync`）。

- **同步引擎**：`agent/vault_sync.py` VaultSyncLoop——20s 纯轮询、`(size,mtime)` 两轮防抖、三向判定（`yuanai_core/pure/vault_note.py` sync_decision：双改本地赢 + 云端版落 `*.conflict-*.md`）、冷启动云端全量建基线、本地删 trash 归档 + 云端删保守墓碑、笔记级重试 + 请求级 20→40→80→300s 退避、状态 `data/vault_sync_state.json`（原子写 + .bak）
- **内容规范**：`vault_note.py` canonical_body 把图片链接统一为 `asset:{mid}/{basename}` 再算哈希（token/写法不同内容相同 → 哈希一致，防无限回环）；自实现 frontmatter（扁平标量，不引 PyYAML）；vault 文件名保留中文空格
- **落盘格式（S3）**：pull 内容里的 `asset:` 链接 → 下载到 `知识星球/assets/{mid}/` 并改写相对路径；frontmatter 锚点（planet_note_id/map_id/tags=星球名/source）；新文件上传成功后只回填 id 段（已有锚点绝不动用户内容）；云端标题变化 → vault 文件改名；本地图片上行未实现（状态报告 images_not_uploaded 计数不静默，S3b）
- **云端地基（S1）**：`api/v1/agent/planet_sync.py`（X-Agent-Id/X-Agent-Secret 鉴权，设备绑定映射，未绑定 403）——/pull/index（含星球名 JOIN）、/pull/content（≤50）、/push/upsert（按 map_id 幂等覆盖 + index_note 重建检索索引）、/push/delete、/asset 下载；planet_notes.content_hash（迁移 0010 + scripts/backfill_note_hash.py，存量空则现算）
- **状态徽标（S4）**：vault_sync_event 经 WS 上报 → `/admin/agent-status` 带 vault_sync 字段 → PlanetPage header 徽标（15s 轮询：已同步 N 篇 / 上传下载冲突计数）；SettingsPage 只读说明卡
- **验证**：`python -m agent.verify_vault_sync`（离线断言 15 项 + --online）；测试 test_vault_note/test_planet_sync_api/test_vault_sync_agent 共 17 项

## 记忆机制（短期工作记忆 + 长期条目化记忆）

「一个对话用到底」：最近 20 条原样保留（工作记忆）；超阈值（>20 条或 >8000 字）由豆包 lite 后台异步折叠成条目化事实（寒暄遗忘、点踩内容剔除）；设置页「我的记忆」卡透明可编辑；记忆注入 system prompt（`chat/router.py` 注入点，桥接与云端直连均生效）。

**记忆文件化（data/.yuan/，Claude Code 式，2026-10-11）**：记忆不再写 MySQL 字段，改为云端工作目录 `data/.yuan/{user_id}/` 文件存储——每条记忆一个 .md（自实现扁平 frontmatter：name/description/type/created_at/source + 正文一行）+ `MEMORY.md` 索引；**写入口只有云端进程**（折叠 worker + API 端点），本地 Agent 工具（remember/get/forget）经 `/api/v1/agent/memory`（agent 凭据）走 HTTP；`users.memory` 字段废弃，首次读时**懒迁移**导出为文件并清空旧字段（`yuanai_core/memory_store.py`：per-user 锁 + 整目录原子替换 + 微秒单调 created_at 保序 + 超限丢最旧）。**工具路径判定（2026-10-12 修复「部署后记忆失效」）按进程身份而非「试连 MySQL」**——试连在用户电脑上会连到本机开发 MySQL、记忆写进本地库云端永远读不到：云端容器（APP_HOME / APP_ENV=production）直连；本地 Agent 的 identity.server_url 指向远程云端 → 强制 HTTP 且 GET/DELETE 必须带 user_id（曾丢 uid 致 400），指向 localhost（本地联调）→ 直连本机库（`yuanai_core/tools/user_memory.py` `_memory_path()`）

- **触发**：`/chat/save` 落库后 fire-and-forget（`api/v1/chat/memory_fold.py`；请求内零成本预筛 + in-flight 防重 + 异常全吞）；工作线程重读 DB 消息数组 → 游标 clamp → 烧钱护栏（≥5 条或 800 字才调 LLM）→ 每日 50 次限额 → 折叠 → 合并 → 游标前进（失败不动自然重试；LLM 空输出=遗忘也前进）
- **游标**：`session_memory_state` 表（session_id PK / folded_count，max 语义只增不减；ai_chat 每次 save 全量重建 id 会变，游标必须是独立前缀计数；编辑重发自动回夹）
- **合并**：`yuanai_core/memory.py` merge_facts 只追加 + **双向去重升级语义**（新行 ⊃ 旧行 → 原地替换不丢细节）+ 上限 100 条/2000 字丢最旧；`parse_facts` 占位词黑名单（无/没有/暂无/（无）等，根治「无」垃圾记忆）
- **智能体自整理（organize_user_memory 工具，2026-10-12）**：模型可自行合并/改写/补充/删除记忆（`plan_organize` 差异推断：清单缺的旧行=删除候选，改写升级复用原 created_at 不洗白）。**删除硬护栏**（安全事故教训）：只删本会话内新增（created_at ≥ 会话首条消息时间，`current_session_id` ContextVar 三处 set：ws_client//stream/claude-stream）、每用户每日删 ≤ `MEMORY_ORGANIZE_DELETE_DAILY_MAX`(3) 条（Redis 计数 `mem_org:{uid}`）、审计日志 `data/logs/memory_audit.log`、任何护栏不过整单拒绝（fail-closed）；本地 Agent 经 `POST /api/v1/agent/memory/organize`（agent 凭据 + user_id + session_id）
- **点踩**：ai_chat_feedback 三态互斥（liked/disliked，迁移 0009）；点踩消息在折叠 transcript 中被剔除并标注
- **编辑入口**：`GET/PUT/DELETE /api/v1/auth/memory`（PUT 超限 400 拒绝而非截断；DELETE 按行文本定位，多条命中 400 不误删）；前端 `MemoryCard.tsx`（每行删除按钮 + 全量编辑抽屉）
- **配置**：config/settings.py MEMORY_* 12 项（模型/窗口/阈值/护栏/上限/超时/日限额，.env 可覆盖）
- 已知限制（二期）：历史仍全量发送模型（不截断省 token）；claude-stream 无记忆注入；/voice/message 不触发折叠

## 计划闭环（2026-10-12，产品定位头号缺口）

「手机定计划、电脑执行」：① 对话制定计划（统筹 `create_plan` 工具拆步骤，只建草稿不自动执行；**本地统筹建计划时尽量绑定 script 工具名+params**）→ ② 云端持久化队列（**用户说「执行」** `execute_plan` 或计划页按钮才 queued；**v1 无定时调度**）→ ③ 本地 Agent `agent/plan_executor.py` 轮询拉取执行（10s 空转；**步骤绑定脚本 → registry.run 零 LLM 直跑**；未绑定（云端 fallback 建的，`.dockerignore` 排除 agent//skills/ 云端无脚本清单）→ bind_tools 一次 LLM 现场选脚本）→ ④ 手机看进度+结果（`/chat/plan` 计划页 3s/15s 轮询 + 结构化渲染）。

- **三表**（迁移 0015）：`plans`（draft/queued/running/done/failed + 冗余计数）/ `plan_steps`（skill 白名单 analysis|collection，automation 挂账；unique(plan_id,step_no)）/ `plan_runs`（**事件溯源 append-only**，只 INSERT——抄 dsh 设计）
- **断点续跑**：认领 = 条件 `UPDATE ... WHERE status='pending'` + rowcount==1 判定（CAS）；同计划严格串行（排除有 running 步骤的计划）；看门狗：认领超时 900s 由 pull 端点惰性重置回 pending、计划级 3600s 无进展判 failed；本地不落状态文件，云端是唯一真相源
- **失败重试**：retryable 且 attempt<2 → 回 pending 自动重试 1 次；确定性失败（无法处理/参数校验失败/未知脚本）不重试；failed 步骤用户可在计划页「重新执行失败步骤」
- **API**：用户侧 JWT `/api/v1/plan/*`（list/detail 带 runs+看门狗/execute 幂等带 agent_online/delete 运行中 409）；Agent 侧设备凭据 `/api/v1/agent/plan/*`（body 不带 user_id 由设备绑定推导，伪造 step_id 被 user_id 冗余校验 404；进度节流 HTTP ≥3s、事件表 ≥10s 或 Δ5%）
- **工具**：`yuanai_core/tools/plan_tools.py`（TOOL_CATEGORY=plan 自动发现）双路径复用 user_memory 的 `_memory_path/_agent_http`；intent_classifier 的 plan_task 平局优先；**计划工具不独立成气泡**（用户拍板，2026-10-14）：sender 归 orchestrator、工具卡挂统筹气泡
- **计划面板独立窗口化（2026-10-15，用户拍板：AI 不自动开关）**：气泡「打开面板」以命名弹窗打开 /chat/plan（`chat/planWindow.ts` 协议 + `chat/usePlanWindow.ts` 模块级单例——同名复用不堆叠、手机端同标签回退、弹窗拦截 navigate 兜底、1s 握手超时强制重载）；**开关完全由用户手动**（窗口内「关闭」按钮）；聊天页顶部「后台执行中」指示条（15s 轮询 queued/running 计划，显示标题与步骤进度，点击同样手动开面板）；弹窗模式 AppLayout 整条顶栏隐藏（完全独立形态）；Landing 入口卡已移除，路由保留作弹窗宿主。分析/自动化面板后续照此推广
- **执行器安全**：skill 白名单 + 托盘开关 callable 实时读 toggles + ScriptRegistry 参数校验；结果三层截断（文本 20K/blocks 200KB/事件 5KB）
- **验证**：`python -m agent.verify_plan [--online]`；pytest test_plan_*.py 五件套；P0 教训：`ScriptRegistry.run` 曾不接受 progress_cb 致委派路径 TypeError（061381a 修复 + test_plan_pure 回归断言锁死）

## 语音对话

火山引擎「AI 音视频互动方案」实时语音（豆包 App 同款：RTC + 豆包 ASR/TTS + 方舟 LLM）：

- 流程：输入区 🎙️ 按钮 → `POST /api/v1/voice/start`（创建 room/task → StartVoiceChat 启动 AI 智能体入房 → 签发 RTC Token）→ 前端 `@volcengine/rtc` SDK joinRoom + 麦克风采集 → 挂断 `POST /api/v1/voice/end`（StopVoiceChat）
- 后端纯 Python 零新依赖：`api/v1/voice/rtc_token.py`（VeRTC Token「001」新版二进制格式，密钥 AppKey）、`v4_sign.py`（OpenAPI V4 签名，域 rtc.volcengineapi.com，Version=2024-12-01）
- 请求体已对齐官方 rtc-server-demo-open 1201 大模型模板（ASR 直接字段 + ApiResourceId=并发版；TTS 走 volcano_bidirection + volc.service_type.10029）；联调参数集中在 `_build_start_body()`
- 前端 `VoiceCall.tsx` 悬浮通话卡（桌面居中 / 手机全屏）：音量波形、通话计时、机器人状态/字幕实时展示（subv/conv 协议）、转录落聊天会话；SDK 动态 import 分包（约 2MB，点击才加载）
- 配置：`.env` 的 VOLCANO_ACCESS_KEY/SECRET_KEY（IAM）、VOLCANO_RTC_APP_ID/APP_KEY（RTC 应用）、VOICE_LLM_ENDPOINT_ID（方舟接入点）、VOICE_ASR/TTS_APP_ID+ACCESS_TOKEN（豆包语音控制台）、VOICE_ASR_RESOURCE_ID（须并发版）、VOICE_TTS_VOICE_BOT（通话机器人音色，主智能体=少年梓辛小男孩）；未配置时 /voice/start 返回 503；**调参**（VolumeGain/StreamMode/end_window_size/MaxTokens/TopP/Prefill 等 12 项）已下沉 `config/settings.py` 的 VOICE_* 常量，`.env` 可覆盖（.env.example 有注释档）
- **气泡朗读（豆包同款，流式边收边播 + 帧协议）**：AI 消息喇叭图标 → `POST /api/v1/voice/tts`（seed-tts-2.0 单向流式）→ 后端 `voice_tts` 边到边转发并**聚合 ≥VOICE_TTS_CHUNK_BYTES(8192) 发帧**（`api/v1/voice/tts_proto.py` 帧协议：kind 1B + len 4B BE，0x01 音频/0x02 错误/0x00 结束；EOF flush 残余 buf；中途失败发显式错误帧不再静默断流）→ 前端 `voiceTtsStream` 帧解析 + **首字节嗅探**兼容旧裸 mp3 → MessageBubble **分段连播**（`toSpeechText` 口语化 + `splitSpeechSegments` ≤200 字/段；串行合成+预取 1 段；**每段一个 Audio 整段播放**，段内不再字节切分根除接缝咔哒）——长文不再截断（原双重 1000 字上限已去），首声延迟 ≈ 首个分片合成
- **语速**：`VOICE_TTS_SPEECH_RATE_BUBBLE`（int [-50,100]，100=2.0x；火山 v3 unidirectional `audio_params.speech_rate`，**与 RTC 双向通道的 float 倍率 `VOICE_TTS_SPEECH_RATE` 语义不同勿混用**）；`VOICE_TTS_MAX_CHARS`（默认 3000，单请求上限）
- **自动朗读开关**：**顶部栏右上角喇叭图标**（豆包同款位置，开=accent 喇叭/关=斜线喇叭）+ 设置页「自动朗读」卡；`hooks/useAutoRead.ts` useSyncExternalStore 跨组件同步（localStorage 键 `autoRead`，**默认开启**，仅显式存 '0' 为关）
- **每 Agent 独立音色**：`config/settings.py` 的 `AGENT_VOICE_MAP`（6 键：orchestrator/local/analysis/collection/automation/claude，默认小元=少年梓辛）；用户设置页（/chat/settings）「语音音色」卡经 `GET/PUT /api/v1/auth/agent-voices` 改 models.json 的 `_agent_voices` 键；`voice_tts` 按消息 sender 查表选音色。**音色须为 2.0 uranus 系列**（1.0 mars 会 55000000 不匹配），预置 12 个音色全部本地实测有效

## 工具系统

- 通用工具：`yuanai_core/tools/` 自动发现，39 个（8 个模块，7 个类别：general/crawl/data/file/memory/knowledge/stats）
- 工具类别标签：每个模块顶部 `TOOL_CATEGORY`，`load_tools_for("crawl", "data")` 按需加载
- Agent 专用工具：`agent/tools/` 递归扫描，38 个（浏览器/审核/Cookie/截图）
- 工具总计：39 共享 + 38 专用 = 80 个，按 Agent 角色精准分配
- 分析脚本：9 个，输出协议：`__IMAGES__` + `__HTML__` + `__RESULT__`
- **联网搜索（2026-10-17 接入官方 API）**：`yuanai_core/pure/web_search.py` 三级兜底——DeepSeek 官方 Search（`POST /v1/tools/search`，结构化结果+权威评级+长摘要，免费过渡期至 11-01 后 5 元/千次成功计费）→ Bing 国内 → DDG 兜底；`_search_deepseek` 复用 DEEPSEEK_API_KEY 鉴权

### 本地 Claude Code 委派工具

`agent/tools/claude_delegate.py` — 统筹 Agent 的 `delegate_to_claude_agent` 工具：以 `claude -p --output-format stream-json` 子进程在**本机仓库**执行代码/终端/Git 任务，30s `progress` 心跳防 SSE 300s 超时，输出截断 8000 字符。

安全边界（重要，2026-09-23 加固后）：
- **三层防线**（不依赖 hook 是否真的在无头模式生效）：
  1. `.claude/settings.json` 已注册 PreToolUse/PostToolUse 钩子（**绝对路径** `$CLAUDE_PROJECT_DIR/scripts/hooks/claude_guard.py`，且 guard 内部 `CLAUDE_CODE_BRIDGE != 1` 时 exit 0 → 对交互会话 no-op，不会锁死）
  2. **fail-closed 门禁**：`bridge_policy.guard_ready()` —— hook 脚本/settings.json 缺失或未注册时，claude_bridge 与 claude_delegate **拒绝 spawn 子进程**
  3. **进程级白名单收敛**：`build_allowed_tools()` 默认不含裸 Bash，只留 `Bash(git status/diff/log、pytest、py_compile:*)` 前缀白名单；`CLAUDE_BRIDGE_ENABLE_BASH=0` 纯只读、`CLAUDE_BRIDGE_BASH_UNRESTRICTED=1` 逃生舱
- 提示词硬约束（黑名单命令清单）+ 审计日志 `data/logs/claude_audit.log` + cwd 锁仓库根 + `--max-budget-usd 10`
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

## Skill 系统（融合后：脚本工具直调）

Agent 能力通过 `skills/` 目录下的 YAML 配置定义：脚本类 skill（analysis/collection）由 `agent/scripts/tools.py` 为每个脚本自动生成 `script_*` StructuredTool 挂统筹（function calling 直调）；automation 保持 react 子 Agent（唯一 delegate）。

```
skills/
├── __init__.py              SkillRegistry 注册中心
├── analysis/skill.yaml      数据分析（模型、脚本目录、兜底提示词）
├── collection/skill.yaml    数据采集（模型、脚本目录、兜底提示词）
└── automation/skill.yaml    自动化（模型、工具列表；唯一 react 子 Agent）
```

每个 `skill.yaml` 包含：名称、描述、模型、运行模式（script_dispatch / react）、脚本目录、兜底系统提示词（计划步骤未绑定脚本时 bind_tools 现场选用）。

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
- 知识库 zip 上传三道闸（条目数/总体积/压缩比/单成员上限 + 逐成员解压 + 路径校验 + 流式写盘 300MB 上限，`api/v1/knowledge/router.py` `_safe_extract_zip`；测试别用 admin/admin123 撞登录——连跑 5 轮会把本地 admin 锁死 15 分钟，conftest 已改自建测试账号）
- **S2 部署面（2026-09-25）**：nginx 安全头收口到 `deploy/snippets/security-headers.conf`（CSP 先 Report-Only）+ `sandbox-headers.conf`（iframe 端点无 XFO）；80 默认块改 301；MySQL 3307 只绑 127.0.0.1（公网关闭，db/merge.py 走 SSH 隧道）；Milvus 不发布端口；Redis requirepass（REDIS_PASSWORD，`db/redis_client.py` + `settings.REDIS_CONFIG` 两处连接点）；应用账号改最小权限（S3.5 随部署执行）

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

**服务器部署**：首次部署跑 `bash deploy/setup-docker.sh`（安装 `deploy/docker-daemon.json` 镜像加速：xuanyuan/1ms/daocloud 三源容错，重启 Docker 并验证拉取 node:18-alpine）；后续更新 `git pull` + `docker compose up -d --build`。国内服务器直连 docker.io 不稳，daocloud 公益源曾 502（2026-10），勿删三源容错结构。

`deploy/Dockerfile.backend` 注意：安装 torch 前必须先预装 `Jinja2`/`typing_extensions`（清华源、精确名称、版本与 requirements.txt 一致）——torch 依赖声明的小写/连字符写法会被新版 pip 严格校验判为不一致，丢弃 pytorch 索引 wheel 转 sdist 构建，而该索引不托管 flit_core 导致构建失败。改动这条 RUN 时勿删预装行。

## 数据分析大屏

分析能力为「脚本工具直调」模式：ScriptRegistry 为 `agent/datanalysis/scripts/` 的每个脚本自动生成 `script_*` 工具（schema 自动生成），统筹 LLM function calling 一次调用选定脚本与参数，经 subprocess 执行（校验咽喉 registry.run）。

**脚本输出协议：**
- `__script_name__` / `__script_tags__` / `__script_params__` — 脚本元数据，ScriptRegistry 自动发现
- `__IMAGES__:path` — 图片输出（脚本 stdout），Registry 转为 base64 嵌入聊天
- `__RESULT__:{json}` — 结构化结果（用于大屏展示），Registry 检测后缓存到文件，通过 `__DASHBOARD__:path` 回传
- `__PROGRESS__:{json}` — 脚本进度（可选，`{"current","total","message"}`）；registry 同时有 10s 时间心跳（存量脚本零改动也有进度）
- 协调器检测 `__DASHBOARD__` → 缓存 Redis（TTL 1h）**并落库 analysis_history** → yield dashboard_event

**A 看板缓存（2026-10-16，脚本运行一次即保存完整看板，未更新直接展示不重跑）：**
- registry 执行前算 `cache_key = md5(脚本源文件 + 规范化参数 + **数据集文件指纹(mtime+size)**)`（`_dashboard_cache_key` / `_dataset_fingerprint`：dataset_id 查库取 file_path；上传覆盖同名文件 → 旧看板自动失效），`data/analysis/dashboards/{key}.html` 命中 → 直接输出 `__DASHBOARD__:{key}` 不启动子进程；未命中执行成功后组装**完整看板 HTML**（__RESULT__ 拍平 KPI 卡前 12 + 各 __HTML__ 图表全文去 plotly CDN script 内联 + plotly.min.js 从本地包 package_data 内联**单文件自包含离线可看**）写缓存
- `__DASHBOARD__` 两态：32hex = 看板缓存 key（orchestrator finditer 区分 → dashboard_event 带 `dashboard_html` 字段）；文件路径 = 原 __RESULT__ JSON（Redis + 历史落库）
- 展示：`GET /api/v1/data/dashboard-html/{key}`（32hex 白名单 + sandbox CSP；全局缓存无 .owner——分析产物非个人数据；middleware `_extract_token` 白名单已加该路径）→ 前端 dashboard 事件有 dashboard_html 时「打开面板」指向轻量页 `/chat/agent/board/:key`（DashboardBoardPage，useSecuredUrl + sandbox iframe）；否则原通用大屏
- **分析历史（2026-10-18 B1-10）**：AnalysisDashboard 页内嵌历史分析列表（消费 `GET /analysis/history`，点击回溯查看历次结果，附「回到最新」）；`/history` 与 `/dashboard/{sid}` 已做会话归属校验（verify_session_owner）；修复 B0 遗留 bug——add_analysis_history 传 script_name 但模型缺列（TypeError 被吞、历史持久化一直失败），迁移 0017 补列
- **停止联动（2026-10-18 B1-11）**：聊天「停止生成」→ SSE 中断 → 云端 `_bridge_sse` CancelledError → `send_stop_to_agent` WS `stop_request` 事件 → 本地 Agent `on_stop_request` → `Orchestrator.cancel_request` → `registry.cancel_running(request_id)` 杀脚本子进程（按 request_id 登记隔离，计划执行器不受影响；脚本返回 `__ERROR__:已停止生成`）
- 已知限制：本地形态成立；跨机/云端挂账（.dockerignore 排除 agent/、无 html 上行通道）；RFM 大屏端点未接（云端无 registry 组装函数）
- 测试：test/test_script_dashboard_cache.py 11 项（hash 命中不重跑/参数与脚本变更重跑/数据集指纹/停止联动杀进程/组装断言/端点白名单）

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
- **iframe 安全（2026-09-25 S1.2 加固）**：iframe 资源用 5 秒 sse token（`GET /auth/sse-token`，单次使用）替代 7 天 JWT 拼 URL（`helpers.tsx useSecuredUrl`）；前端 5 处 iframe 全部 `sandbox="allow-scripts"`；后端三个 HTML 端点（planet origin / analysis-html / script-html）响应 `CSP: sandbox allow-scripts; frame-ancestors 'self'` + nosniff；script-html 增加 html_id 白名单（12 位 hex）+ `.owner` 归属校验（registry 生成时写入 current_user_id）；middleware 冻结检查改读 request.state.user_id（sse 分支原静默失效）

**医学 API（`api/v1/medical/router.py`，JWT 保护）：**
- `GET /api/v1/medical/species` — 物种→MeSH 导航列表
- `GET /api/v1/medical/search?q=&max=` — PubMed 文献检索（esearch+efetch，NCBI 失败返回 502）
- `POST /api/v1/medical/feasibility` — 药物可行性评估（LLM，verdict 高/中/低 + 理由 + 置信度）

**内置工具（Agent 可直接调用）：**
- `list_datasets` / `preview_dataset` / `analyze_dataset` — 数据集管理
- `transform_dataset` / `describe_column` / `correlate_columns` — 数据转换与分析
