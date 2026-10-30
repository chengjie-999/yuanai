export const AGENT_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  orchestrator: { label: '小元AI', color: '#2563eb', bg: '#eff6ff' },
  // 统一身份：本地模式不再暴露「本机」后缀（用户体验拍板 2026-10-15，
  // 豆包式——执行位置对用户透明，离线回退提示语承担差异化）
  local: { label: '小元AI', color: '#2563eb', bg: '#eff6ff' },
  // 融合后：analysis/collection 不再是独立 Agent，仅历史会话气泡复用键位
  analysis: { label: '数据分析', color: '#7b1fa2', bg: '#faf5ff' },
  collection: { label: '数据采集', color: '#00695c', bg: '#f0faf9' },
  automation: { label: '自动化 Agent', color: '#e65100', bg: '#fff8f0' },
  claude: { label: 'Claude Code', color: '#d97757', bg: '#fdf6f0' },
  planet: { label: '知识星球', color: '#6a9955', bg: '#f2f8f0' },
  plan: { label: '计划', color: '#0b7285', bg: '#eef7fa' },
}

// 团队能力矩阵（LandingPage/AgentPage/后台 AgentsTab 三处数据源）：
// 融合后 = 统筹（内置脚本工具）+ 自动化 + Claude Code
export const SUB_AGENTS = [
  { key: 'orchestrator', label: '统筹 Agent', desc: '内置数据分析/采集/生命科学脚本工具，一问直调', color: '#2563eb' },
  { key: 'automation', label: '自动化 Agent', desc: '浏览器控制、题目审核、截图监控（多步自主）', color: '#e65100' },
  { key: 'claude', label: 'Claude Code', desc: '本机代码编写、终端命令、Git 操作', color: '#d97757' },
]

export function senderFromTool(name: string): string | null {
  // 旧 delegate 名保留识别（历史会话信封兼容）；新链路脚本工具不再开独立气泡
  if (name.startsWith('delegate_to_analysis')) return 'analysis'
  if (name.startsWith('delegate_to_collection')) return 'collection'
  if (name.startsWith('delegate_to_automation')) return 'automation'
  if (name.startsWith('delegate_to_claude')) return 'claude'
  if (name === 'retrieve_planet_knowledge') return 'planet'
  // 计划工具（create_plan/execute_plan/get_plan_status）不独立成气泡：
  // 工具卡挂统筹气泡（用户拍板），气泡挂「打开面板」链 /chat/plan
  return null
}

// 脚本工具 key → 中文标签（ToolCallCard 显示用；与 agent/scripts/registry.py SCRIPT_KEYS 对偶）
export const SCRIPT_LABELS: Record<string, string> = {
  script_descriptive_stats: '描述性统计分析',
  script_correlation: '相关性分析',
  script_regression: '回归分析',
  script_categorical: '分类数据分析',
  script_timeseries: '时间序列分析',
  script_preprocess: '数据预处理',
  script_rfm_cluster: 'RFM 客户分群',
  script_churn_predict: '客户流失预测',
  script_gene_expression: '基因表达分析',
  script_generic_crawl: '通用网页采集',
}

// 工作模式推荐问题（2026-10-31 用户拍板：全部换成云端可直接完成的提示词——
// 普通用户（本地 Agent 可能未安装/离线）点任意一条都能直接得到完整结果；
// 脚本分析/自动化等本地能力不再出现在推荐位，由用户主动发起）
export const SUGGESTIONS: { text: string; desc: string }[] = [
  { text: '帮我搜索一下最新的AI大模型动态', desc: '联网搜索 · 最新资讯' },
  { text: '帮我制定一份本周的学习计划', desc: '计划拆分 · 云端直接完成' },
  { text: '写一篇数据分析入门指南', desc: '写作 · 云端直接完成' },
  { text: '用 HTML 写一篇 500 字的文章', desc: 'HTML 直渲 · 云端直接完成' },
  { text: '帮我写一段爬虫的 Python 代码', desc: '代码生成 · 云端直接完成' },
  { text: '推荐几本学习数据分析的书', desc: '联网搜索 · 书单推荐' },
  { text: '帮我翻译一段英文', desc: '翻译 · 云端直接完成' },
  { text: '帮我规划一次五天的旅行行程', desc: '计划拆分 · 云端直接完成' },
]

// 娱乐模式开场话题（E5）：C 端陪伴导向——吃瓜/安利/脑洞，搜索与记忆驱动
export const ENT_SUGGESTIONS: { text: string; desc: string }[] = [
  { text: '最近娱乐圈有什么瓜？', desc: '联网搜索 · 最新热点' },
  { text: '最近有什么好看的电影和剧？', desc: '联网搜索 · 追剧安利' },
  { text: '给我讲个有趣的段子', desc: '脑洞创作 · 陪聊解闷' },
  { text: '推荐几首适合通勤听的歌', desc: '音乐推荐 · 陪伴' },
  { text: '帮我起个有意思的游戏ID', desc: '脑洞创作 · 玩梗' },
  { text: '今天有什么值得关注的新闻？', desc: '联网搜索 · 新鲜资讯' },
]
