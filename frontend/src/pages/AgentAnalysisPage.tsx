import { Link } from 'react-router-dom'
import AnalysisPanel from '../components/chat/panels/AnalysisPanel'
import { AGENT_CONFIG } from '../config/agents'
import { ArrowLeftIcon, BarChartIcon } from '../components/icons'

export default function AgentAnalysisPage({ onClose, hideBack }: { onClose?: () => void; hideBack?: boolean } = {}) {
  const agent = AGENT_CONFIG.analysis

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--bg-secondary)' }}>
      <div style={{
        padding: '8px 12px', background: 'var(--header-bg)', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
      }}>
        {hideBack ? null : onClose ? (
        <button onClick={onClose} style={{
          fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none',
          padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border)',
          flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4, lineHeight: 1,
          background: 'transparent', cursor: 'pointer',
        }}><ArrowLeftIcon size={12} /> 返回对话</button>
      ) : (
        
      )}
        <span style={{ lineHeight: 1, color: agent.color, display: 'flex' }}><BarChartIcon size={18} /></span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: agent.color }}>数据分析 Agent</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>数据集管理、统计分析、图表生成</div>
        </div>
      </div>
      <div className="agent-page-body" style={{ flex: 1, overflow: 'auto', maxWidth: 900, margin: '0 auto', width: '100%', boxSizing: 'border-box' }}>
        <AnalysisPanel />
      </div>
    </div>
  )
}
