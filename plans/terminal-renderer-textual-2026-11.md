# 终端渲染层升级方案：rich 全帧重绘 → Textual diff 渲染（2026-11-12 立项，用户实测反馈驱动）

**来源（用户原话）**：「消息步骤太多，上面固定不行，都抽搐了，而且鼠标不能滑动。设计一下优化方案吧。还有我问一下这终端你是用啥写的，用 js 会好点吗，借鉴一下 cc 吧」

## 1. 现状问题定位（为什么抽搐、为什么没鼠标）

| 现象 | 根因 |
|------|------|
| 消息多时「抽搐」 | rich `Live(12fps)` + `redraw()` 都是**全帧重绘**——每个 token、每次刷新都把全部块重新渲染+清屏重打。消息块一多（几十个），每帧都要重画整个屏幕，视觉上就是抖动/闪屏 |
| 鼠标不能滑动 | 手写块系统只有键盘（↑↓/PgUp/PgDn），没有鼠标事件解析（SGR mouse mode 要手写） |
| 顶栏「固定」不牢 | 靠清屏重打印模拟固定，帧与帧之间可见闪动 |
| 滚动回看污染 | 已用 alt-screen 隔离（scrollback 干净），但 alt-screen 内仍无鼠标滚轮 |

## 2. 技术选型回答（用户问「用 js 会好点吗」）

- **现状栈**：Python——渲染 rich（全帧），输入 prompt_toolkit。终端与 Agent 同进程（复用 chat_client / claude_loop / 审批流 / pet_events / 会话存储零成本）。
- **JS 方案成本**：CC 用 TypeScript+Ink 是因为它本身是 Node 生态。我们换 JS = 拆两进程 + JS 重写 chat_client/claude_loop/审批/桌宠联动 + 双运行时部署——是「重写整个终端」而非优化，排除。
- **Python 界的 CC 对应物 = Textual**：widget 组件树 + **diff 渲染（只重绘变化的 widget，token 流只更新 answer 组件）** + 原生鼠标滚轮 + 固定 Header/Footer 布局 + 内置测试工具（pilot）。三个痛点全是它的原生能力。v3 当初排除它（「框架重写成本」），现被实测反馈推翻——**换渲染层，不换语言**。
- **借鉴 CC 的产品形态**：固定顶栏 / 可滚动正文 / 底部输入 dock / 鼠标滚轮+拖拽滚动条 / 流畅无闪屏。

## 3. 目标形态（Textual App）

```
┌ 状态栏（Header widget，常驻不重绘）────────────────────────────┐
│ ●在线 /claude · 工作目录 · 会话号 · 宠:thinking · F2 · ? 帮助   │
├ 对话流（ScrollView，鼠标滚轮/拖拽/键盘原生）───────────────┬───┤
│ ▸ 思考 (12s) · 2 次工具调用        [折叠块]                 │执行│
│ ▸ ⚙ bash $ git status             [工具卡]                 │观测│
│ 回答正文（Markdown widget，流式只重绘这一段）               │右栏│
├──────────────────────────────────────────────────────────┴───┤
│ ▌ 输入 dock（Input widget，↑↓历史/斜杠补全）                   │
└────────────────────────────────────────────────────────────────┘
```

- Header：只渲染一次，状态变化（在线点/后端/pet）单独更新 header 的 Text
- Body：ScrollView + 块列表（thinking 折叠块/tool 卡/answer Markdown/plan 视图）；token 流只触发 answer widget 的 update（diff 到行级，无闪屏）
- 右栏「执行观测」：竖排 Static widget（观测轮询 15s 只更新这几行）
- 输入：Textual Input（历史/补全沿用现有逻辑；Esc+Enter 换行、多行粘贴）——替换 prompt_toolkit（审批 Y/N 改成 Textual 内 modal 提示）
- alt-screen：Textual 原生（进/出自动），scrollback 保持干净
- 管道模式 / PlainRenderer / RichRenderer 回退链**不动**（Textual 不可用时降级路径照旧；#13 VT 自愈保证 WT/自建控制台可用）

## 4. 复用边界（重写面收敛）

| 层 | 处置 |
|----|------|
| chat_client（云端通道）/ claude_loop（/claude SDK）/ 审批决议 / 计划客户端 / 观测轮询线程 / pet_events / 会话存储 / web_chat_url / cc_workspace | **全复用零改动** |
| run_cloud_query / run_query 事件消费 | 复用，仅把 renderer 接口（token/reasoning/tool_start/…）接到 Textual 组件上——**接口形状不变** |
| FullscreenRenderer（块渲染/滚动/折叠/Live 帧） | 重写为 Textual App（约 800-1000 行，含测试） |
| run_repl 主循环（ptk prompt/哨兵 _REFRESH/keybinding） | 重写为 App 事件循环（Textual 自带 input 事件；_REFRESH 哨兵机制退役） |
| _ptk_approve / _make_ptk_prompt | 退役（审批改 App 内 modal） |
| 测试 | test_terminal_fullscreen 的块语义断言保留（映射到 widget 状态）；渲染断言换 Textual pilot（App.run_test） |

## 5. 分期

- **P0 框架替换（核心）**：Textual App 三区布局 + 块渲染迁移 + token 流式 diff + 输入 dock；键盘交互（↑↓/Enter 展开折叠/PgUp/PgDn/Esc）对齐现状；审批 modal；观测右栏/计划视图迁移。验收=长会话 100+ 块无闪屏
- **P1 鼠标与滚动打磨**：鼠标滚轮/拖拽滚动条/点击折叠块；状态栏鼠标悬停提示；流畅度参数调优（每 token 刷新节流）
- **P2 高级交互（原 #39 品牌批合并）**：主题色板对齐网站（Textual CSS 变量，明暗自动）、吉祥物彩蛋、斜杠命令补全强化、Ctrl+R 历史搜索迁移

## 6. 风险与决策点

- **决策点 A（用户拍板）**：引入 Textual 依赖（纯 Python、零系统依赖，pip 一个包；exe 打包体积 +~2MB）——**我的建议：拍板用 Textual**，备选=手写 diff 渲染+手写鼠标解析（工作量大且不彻底）
- 风险 1：Textual 学习成本/文档——一次性，测试工具齐全
- 风险 2：与现状降级链的兼容——Textual 启动失败（无 VT 的老控制台）自动回退现有 RichRenderer 路径（保留）
- 风险 3：exe 打包——spec 加 textual 依赖（hiddenimports 注意 tcss 资源文件，打包时验证）
- 风险 4：审批流从 ptk 迁移——modal 替代 Y/N，语义不变（120s 超时默认 deny）

## 7. 关联

- 现状实现：agent/terminal.py（FullscreenRenderer/RichRenderer/PlainRenderer/run_repl）
- 测试基线：test_terminal_fullscreen.py 27 项（块语义断言将保留为 widget 状态断言）
- 后续队列：#39 v3.3 品牌（与 P2 合并）→ #41 WT 内嵌 → #30 消息 id
- 用户原则对齐：「借鉴 CC 产品形态，不换语言不推倒重来」——复用面最大化，重写面收敛在渲染层
