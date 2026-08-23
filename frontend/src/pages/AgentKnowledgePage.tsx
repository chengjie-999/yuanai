import { Link } from 'react-router-dom'
import KnowledgePanel from '../components/chat/panels/KnowledgePanel'

export default function AgentKnowledgePage() {
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
        <span style={{ fontSize: 18, lineHeight: 1 }}>📚</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--accent)' }}>知识库</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>知识库检索与文档查询</div>
        </div>
      </div>
      <div className="agent-page-body" style={{ flex: 1, overflow: 'auto', maxWidth: 900, margin: '0 auto', width: '100%', boxSizing: 'border-box' }}>
        <KnowledgePanel />
      </div>
    </div>
  )
}
