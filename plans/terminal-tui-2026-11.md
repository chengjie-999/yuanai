# 终端 TUI v3 设计方案（2026-11-11 立项，来源：用户「终端界面比较简陋，该怎么设计」）

**定位**：yuan 终端 = 本地 Agent 的 CC 式终端（桌面主动对话入口、桌宠搭档）。v2 是「线性 REPL + Markdown 渲染」——能用但简陋；v3 升级为**全屏 TUI**，风格与网站对齐，但**不复刻 CC 全功能**（只补体验核心）。

**原则**：
1. **rich + prompt_toolkit 渐进升级，不引 Textual**——框架完整但要重写全部渲染/输入/测试层，rich 的 Layout/Fullscreen 已够用
2. **纯文本回退永远保留**（管道模式 / Git Bash mintty 无 winpty / 服务器 SSH）——渲染层抽象（Plain/Rich）已存在，v3 只是 RichRenderer 的增强
3. **与已有资产联动，不另起炉灶**：观测数据用 /chat/cc-activity（已有）、计划用 agent 设备凭据端点（已有）、桌宠 pet_events（已有）、设置面板 URL（已有）

## 现状盘点（v2 能力，均已落地）

| 能力 | 现状 |
|---|---|
| 渲染 | RichRenderer（Markdown/代码着色/面板块）+ PlainRenderer（管道/回退），思考 dim 斜体 |
| 输入 | prompt_toolkit（多行 Enter 提交 / Esc+Enter 换行 / ↑↓ 历史 / Ctrl+C 停止语义） |
| 模式 | /claude（SDK loop，与云端桥接同路径）/ /chat（本地 LLM 流式） |
| 命令 | /history /clear /quit /help /claude /chat |
| 联动 | 桌宠六态 pet_events、会话续接 terminal_sessions.json、--no-agent（发布版内置终端防双连） |
| 发布 | 已随 exe 打包（20261112 起发布版内置终端） |

**缺**：全屏布局（无状态栏/无分区）、无观测面、无命令补全、无消息级操作、无品牌视觉。

## 布局设计（v3.0）

```
┌──────────────────────────────────────────────────────────────┐
│ ●在线  /claude  · D:\code\yuanai  · 会话#3  · ? 帮助  · [桌宠状态] │ ← 状态栏（静态）
├──────────────────────────────────────────────────────────────┤
│ 对话流（滚动区）                                              │
│  ▸ 思考 (12s) · 2 次工具调用        [折叠块，默认收起]        │
│  ▸ Bash  $ git status               [工具卡紧凑行]           │
│  回答正文（Markdown 渲染）+ 流式光标 ▍                         │
│                                              ┌─────────────┐ │
│                                              │ 执行观测面   │ │ ← 右栏（可选）
│                                              │ Bash… 3s前   │ │    v3.2
│                                              │ 空闲 2min    │ │
│                                              └─────────────┘ │
├──────────────────────────────────────────────────────────────┤
│ ▌ 多行输入（自动增高）  /plan /status 补全弹层 [Tab 补全]      │ ← 输入区（dock）
└──────────────────────────────────────────────────────────────┘
```

**状态栏数据源**（--no-agent 发布版形态下没有 WS 连接，设计必须兼容）：
- 在线态 = 本机 run_agent handle（源码 yuan 形态）或 15s 轮询 `/chat/cc-activity`（--no-agent 形态，已有端点）
- 工作目录 = cc_workspace.resolve_project_dir（已有）；会话 id = TerminalSessionStore
- 桌宠状态 = pet_events 最近事件（可选）

**渲染实现**：`RichRenderer` 增加全屏模式——`Console(screen=True)` + `rich.layout.Layout`（header/body/input 三行，header 固定高度、input 随 prompt_toolkit 换行自适应、body 弹性）+ resize 事件重建布局。流式回答渲染到 body 的 markdown 容器；思考/工具卡沿用现有分段数据结构，改为**折叠块**渲染（同网页「思考 (Xs) · N 次工具调用」语义，回车展开）。纯文本回退分支零改动。

## 交互设计（v3.1）

| 项 | 设计 | 实现要点 |
|---|---|---|
| 斜杠命令补全 | 输入 `/` 弹候选（ptk `WordCompleter` 动态） | 命令表扩展：`/plan`（计划队列，走 `/api/v1/agent/plan/*` 设备凭据端点——终端无用户 JWT，设备凭据是唯一可用身份）/ `/status`（本机状态）/ `/panel`（webbrowser 开设置面板）/ `/pet on|off`（pet_events launch/stop）/ `/sessions`（会话列表选择切换，TerminalSessionStore） |
| 审批富卡片 | review 命令 Y/N 升级为 Panel 卡片：命令高亮、风险色（allow 绿/review 黄/deny 红）、120s 倒计时、默认 deny | `_ptk_approve` 改为主循环内富卡片（ptk prompt_async 换 Live 显示） |
| 历史消息操作 | `Ctrl+R` 搜索历史；选中后 `Ctrl+C` 复制 / Enter 重发 | ptk 自定义键位 |
| 帮助浮层 | `?` 键弹快捷键总览浮层 | Modal 层 |

## 观测联动（v3.2，愿景「手机看电脑在干什么」桌面侧）

- 右栏「执行观测面」：15s 轮询 `/chat/cc-activity`（已有端点，含最近活动 + age_s）渲染最近 5 条活动 + 空闲/执行状态色点；超过 5 分钟无活动黄条提示（与网页同语义）
- `/plan` 全屏视图：queued/running 计划列表 + 步骤进度条（rich Progress 列）
- 桌宠事件流（pet_events 六态）进状态栏色点

## 品牌对齐（v3.3）

- **色板**：网站变量同值（蓝 accent #2563eb、棕 CC #d97757、灰兜底 #64748b、success/danger/warning）——终端内常量与 frontend CSS 变量对偶，改一处同步
- **主题跟随**：优先读本机缓存 `data/theme.json`（Agent 进程 set_theme 时写）；缓存缺失读终端环境探测（WT/COLORTERM）；**云端下发**新增 `/api/v1/agent/my-theme`（设备凭据 → 绑定用户 users.theme，与 /agent/my-profile 同模式）——终端启动拉一次即与网站明暗一致
- **吉祥物彩蛋**：状态栏 braille 字符 + 渐变色阶渲染呼吸核心球（纯文本回退跳过）

## 依赖与发布

- 全部 Agent 侧（rich/ptk 已入 spec 20261112），**与其它 Agent 侧改动合并一次打包**（用户拍板「全部完成后再统一打包」）
- 云端仅 v3.3 可选新增一个设备凭据端点 `/agent/my-theme`（小）
- 测试：test_terminal.py 现有 21 项保持（Plain 路径）；v3 新增渲染注入测试（`Console(record=True)` 快照断言布局三区/折叠块/状态栏）+ 命令补全表单测 + /plan 端点 mock 测试

## 验收路径（傻瓜标准）

托盘「终端对话」→ 全屏三区（状态栏在线绿点/工作目录/会话号）→ /claude 跑「git status」→ 折叠块展开可见工具卡 → 右栏出现刚才的 Bash 活动 → 明暗与网站一致 → 管道模式（echo 单轮）仍纯文本可用。
