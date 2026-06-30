import type { ToolCall } from '../types'

function AnimatedDot() {
  return (
    <span style={{ display: 'inline-flex', gap: 2, marginLeft: 4 }}>
      <span style={{ width: 4, height: 4, borderRadius: '50%', background: '#999', animation: 'pulse 1s ease-in-out infinite' }} />
      <span style={{ width: 4, height: 4, borderRadius: '50%', background: '#999', animation: 'pulse 1s ease-in-out 0.2s infinite' }} />
      <span style={{ width: 4, height: 4, borderRadius: '50%', background: '#999', animation: 'pulse 1s ease-in-out 0.4s infinite' }} />
    </span>
  )
}

const statusConfig = {
  running: { label: '执行中', dotColor: '#f5a623' },
  done: { label: '完成', dotColor: '#4caf50' },
  error: { label: '失败', dotColor: '#f44336' },
}

const AGENT_LABELS: Record<string, { label: string; color: string }> = {
  delegate_to_analysis_agent: { label: '数据分析 Agent', color: '#58a6ff' },
  delegate_to_collection_agent: { label: '数据采集 Agent', color: '#3fb950' },
  delegate_to_automation_agent: { label: '自动化 Agent', color: '#d29922' },
  list_datasets: { label: '列出数据集', color: '#bc8cff' },
  preview_dataset: { label: '预览数据', color: '#bc8cff' },
  analyze_dataset: { label: '分析数据', color: '#bc8cff' },
  fetch_url: { label: '抓取网页', color: '#3fb950' },
  parse_html: { label: '解析 HTML', color: '#3fb950' },
}

function ToolCallCard({ call }: { call: ToolCall }) {
  const cfg = statusConfig[call.status] || statusConfig.done
  const agent = AGENT_LABELS[call.name]
  const displayName = agent ? agent.label : call.name

  return (
    <div style={{
      marginTop: 8, marginBottom: 4, borderRadius: 10,
      border: agent ? `1px solid ${agent.color}44` : '1px solid var(--border)',
      overflow: 'hidden', fontSize: 13, background: 'var(--bg-tertiary)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 12px',
        background: call.status === 'running' ? 'var(--accent-light)' : 'transparent',
      }}>
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
      </div>
      {call.status === 'done' && call.result && (
        <div style={{
          padding: '8px 12px', borderTop: '1px solid var(--border-light)',
          color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.5,
          maxHeight: 60, overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {call.result.length > 120 ? call.result.slice(0, 120) + '...' : call.result}
        </div>
      )}
      {call.status === 'error' && (
        <div style={{
          padding: '8px 12px', borderTop: '1px solid var(--border-light)',
          color: 'var(--danger)', fontSize: 12,
        }}>
          {call.result}
        </div>
      )}
    </div>
  )
}

export default ToolCallCard
