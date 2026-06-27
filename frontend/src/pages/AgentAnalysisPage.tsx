import { Link } from 'react-router-dom'
import AnalysisPanel from '../components/chat/panels/AnalysisPanel'
import { AGENT_CONFIG } from '../config/agents'

export default function AgentAnalysisPage() {
  const agent = AGENT_CONFIG.analysis

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#fafafa' }}>
      <div style={{
        padding: '10px 20px', background: '#fff', borderBottom: '1px solid #e8e8ec',
        display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0,
      }}>
        <Link to="/" style={{
          fontSize: 12, color: '#999', textDecoration: 'none',
          padding: '4px 10px', borderRadius: 6, border: '1px solid #e0e0e0',
          transition: 'color 0.15s',
        }}>← 返回对话</Link>
        <span style={{ fontSize: 18, lineHeight: 1 }}>📊</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: agent.color }}>数据分析 Agent</div>
          <div style={{ fontSize: 11, color: '#999' }}>数据集管理、统计分析、图表生成</div>
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'auto', maxWidth: 900, margin: '0 auto', width: '100%', padding: 20, boxSizing: 'border-box' }}>
        <AnalysisPanel />
      </div>
    </div>
  )
}
