import { Link } from 'react-router-dom'
import AnalysisPanel from '../components/chat/panels/AnalysisPanel'
import { AGENT_CONFIG } from '../config/agents'

export default function AgentAnalysisPage() {
  const agent = AGENT_CONFIG.analysis

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--bg-secondary)' }}>
      <div style={{
        padding: '8px 12px', background: 'var(--header-bg)', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
      }}>
        <Link to="/chat" style={{
          fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none',
          padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border)',
          flexShrink: 0,
        }}>← 返回</Link>
        <span style={{ fontSize: 18, lineHeight: 1 }}>📊</span>
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
