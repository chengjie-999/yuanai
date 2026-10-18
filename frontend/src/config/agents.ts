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

export const SUGGESTIONS: { text: string; desc: string }[] = [
  { text: '帮我搜索一下最新的AI大模型动态', desc: '联网搜索 · 搜索+抓取+解析' },
  { text: '帮我制定：先抓取网页数据再做统计分析的执行计划', desc: '计划闭环 · 手机定 / 电脑执行' },
  { text: '帮我做RFM客户价值分群', desc: '脚本直调 · 客户分群 → 3D大屏' },
  { text: '对我的数据集做描述性统计分析', desc: '脚本直调 · 统计 + 图表 + 大屏' },
  { text: '帮我预测客户流失情况', desc: '脚本直调 · 逻辑回归预测 → 大屏' },
  { text: '分析特征之间的相关性', desc: '脚本直调 · 相关系数 + 热力图' },
  { text: '帮我做数据预处理和清洗', desc: '脚本直调 · 缺失值 + 标准化' },
  { text: '对时间序列数据做趋势分析', desc: '脚本直调 · STL分解 + 异常检测' },
  { text: '抓取这个网页的内容', desc: '脚本直调 · 网页爬取抓取' },
  { text: '帮我审核小猿众包题目', desc: '自动化 · 浏览器操控' },
  { text: '搜索知识库中的技术文档', desc: '知识库 · 可打开独立面板' },
]
