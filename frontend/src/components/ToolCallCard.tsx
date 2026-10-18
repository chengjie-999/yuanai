import { useState } from 'react'
import type { ToolCall } from '../types'
import { SCRIPT_LABELS } from '../config/agents'
import MarkdownContent from './MarkdownContent'
import { ChevronDownIcon, ChevronUpIcon } from './icons'

function AnimatedDot() {
  return (
    <span style={{ display: 'inline-flex', gap: 2, marginLeft: 4 }}>
      <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--text-muted)', animation: 'pulse 1s ease-in-out infinite' }} />
      <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--text-muted)', animation: 'pulse 1s ease-in-out 0.2s infinite' }} />
      <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--text-muted)', animation: 'pulse 1s ease-in-out 0.4s infinite' }} />
    </span>
  )
}

const statusConfig = {
  running: { label: '执行中', dotColor: 'var(--warning)' },
  done: { label: '完成', dotColor: 'var(--success)' },
  error: { label: '失败', dotColor: 'var(--danger)' },
}

const AGENT_LABELS: Record<string, { label: string; color: string }> = {
  delegate_to_automation_agent: { label: '自动化 Agent', color: '#d29922' },
  delegate_to_claude_agent: { label: 'Claude Code', color: '#d97757' },
  list_datasets: { label: '列出数据集', color: '#bc8cff' },
  preview_dataset: { label: '预览数据', color: '#bc8cff' },
  analyze_dataset: { label: '分析数据', color: '#bc8cff' },
  fetch_url: { label: '抓取网页', color: '#3fb950' },
  parse_html: { label: '解析 HTML', color: '#3fb950' },
  search_web: { label: '联网搜索', color: '#58a6ff' },
  create_plan: { label: '制定计划', color: '#0b7285' },
  execute_plan: { label: '执行计划', color: '#0b7285' },
  get_plan_status: { label: '查询计划', color: '#0b7285' },
  search_pubmed: { label: 'PubMed 检索', color: '#00897b' },
  get_species_info: { label: '物种导航', color: '#00897b' },
  assess_drug_feasibility: { label: '药物可行性', color: '#00897b' },
  search_clinical_trials: { label: '临床试验检索', color: '#00897b' },
  get_article_detail: { label: '文献详情', color: '#00897b' },
}

function toolLabel(name: string): { label: string; color: string } | null {
  const hit = AGENT_LABELS[name]
  if (hit) return hit
  const script = SCRIPT_LABELS[name]
  if (script) return { label: script, color: '#bc8cff' }
  return null
}

function ToolCallCard({ call }: { call: ToolCall }) {
  const cfg = statusConfig[call.status] || statusConfig.done
  const agent = toolLabel(call.name)
  const displayName = agent ? agent.label : call.name
  const [expanded, setExpanded] = useState(false)
  const raw = call.result || ''
  const showBody = call.status === 'done' && !!raw
  const expandable = showBody && raw.length > 160
  const preview = expandable && !expanded ? raw.slice(0, 160).trim() + '…' : raw

  return (
    <div style={{
      marginTop: 8, marginBottom: 4, borderRadius: 10,
      border: agent ? `1px solid ${agent.color}44` : '1px solid var(--border)',
      overflow: 'hidden', fontSize: 13, background: 'var(--bg-tertiary)',
    }}>
      {/* 头部：状态点 + 中文标签 + 状态（长结果可点击展开/收起） */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '7px 12px',
        background: call.status === 'running' ? 'var(--accent-light)' : 'transparent',
        cursor: expandable ? 'pointer' : 'default',
      }} onClick={expandable ? () => setExpanded((e) => !e) : undefined}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%', background: cfg.dotColor,
          flexShrink: 0,
        }} />
        <span style={{ fontWeight: 600, color: agent ? agent.color : 'var(--text-primary)', fontSize: 13, flex: 1 }}>
          {displayName}
        </span>
        <span style={{ fontSize: 12, color: cfg.dotColor, fontWeight: 500, flexShrink: 0 }}>
          {call.status === 'running' ? (
            <span style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              {cfg.label}<AnimatedDot />
            </span>
          ) : cfg.label}
        </span>
        {expandable && (
          <span style={{ display: 'flex', color: 'var(--text-muted)', flexShrink: 0 }}>
            {expanded ? <ChevronUpIcon size={13} /> : <ChevronDownIcon size={13} />}
          </span>
        )}
      </div>
      {/* 结果区：markdown 渲染（搜索结果链接可点击、表格/列表正常排版），
          默认折叠预览，点击头部展开（内部滚动） */}
      {showBody && (
        <div style={{
          padding: '6px 12px 10px', borderTop: '1px solid var(--border-light)',
          color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6,
          maxHeight: expanded ? 240 : 64, overflow: expanded ? 'auto' : 'hidden',
        }}>
          <MarkdownContent content={preview} />
        </div>
      )}
      {call.status === 'error' && (
        <div style={{
          padding: '8px 12px', borderTop: '1px solid var(--border-light)',
          color: 'var(--danger)', fontSize: 12, lineHeight: 1.6,
        }}>
          {call.result}
        </div>
      )}
    </div>
  )
}

export default ToolCallCard
