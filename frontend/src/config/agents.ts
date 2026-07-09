export const AGENT_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  orchestrator: { label: '小元AI', color: '#1976d2', bg: '#f0f5ff' },
  analysis: { label: '数据分析 Agent', color: '#7b1fa2', bg: '#faf5ff' },
  collection: { label: '数据采集 Agent', color: '#00695c', bg: '#f0faf9' },
  automation: { label: '自动化 Agent', color: '#e65100', bg: '#fff8f0' },
}

export const SUB_AGENTS = [
  { key: 'orchestrator', label: '统筹 Agent', desc: '意图识别与任务分发', color: '#1976d2' },
  { key: 'analysis', label: '数据分析 Agent', desc: '数据集管理、统计分析、图表生成', color: '#7b1fa2' },
  { key: 'collection', label: '数据采集 Agent', desc: '网页爬取、数据抓取、内容提取', color: '#00695c' },
  { key: 'automation', label: '自动化 Agent', desc: '浏览器控制、题目审核、截图监控', color: '#e65100' },
]

export function senderFromTool(name: string): string | null {
  if (name.startsWith('delegate_to_analysis')) return 'analysis'
  if (name.startsWith('delegate_to_collection')) return 'collection'
  if (name.startsWith('delegate_to_automation')) return 'automation'
  return null
}

export const SUGGESTIONS: { text: string; desc: string }[] = [
  { text: '帮我做RFM客户价值分群', desc: '数据分析 · 客户分群 → 3D大屏' },
  { text: '对我的数据集做描述性统计分析', desc: '数据分析 · 统计 + 图表 + 大屏' },
  { text: '帮我预测客户流失情况', desc: '数据分析 · 逻辑回归预测 → 大屏' },
  { text: '分析特征之间的相关性', desc: '数据分析 · 相关系数 + 热力图' },
  { text: '帮我做数据预处理和清洗', desc: '数据分析 · 缺失值 + 标准化' },
  { text: '对时间序列数据做趋势分析', desc: '数据分析 · STL分解 + 异常检测' },
  { text: '抓取这个网页的内容', desc: '数据采集 · 网页爬取抓取' },
  { text: '帮我审核小猿众包题目', desc: '自动化 · 浏览器操控' },
  { text: '搜索知识库中的技术文档', desc: '知识库 · 可打开独立面板' },
]
