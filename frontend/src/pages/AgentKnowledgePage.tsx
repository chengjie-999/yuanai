import { Link } from 'react-router-dom'
import KnowledgePanel from '../components/chat/panels/KnowledgePanel'

export default function AgentKnowledgePage() {
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#fafafa' }}>
      <div style={{
        padding: '10px 20px', background: '#fff', borderBottom: '1px solid #e8e8ec',
        display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0,
      }}>
        <Link to="/" style={{
          fontSize: 12, color: '#999', textDecoration: 'none',
          padding: '4px 10px', borderRadius: 6, border: '1px solid #e0e0e0',
        }}>← 返回对话</Link>
        <span style={{ fontSize: 18, lineHeight: 1 }}>📚</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#1565c0' }}>知识库</div>
          <div style={{ fontSize: 11, color: '#999' }}>知识库检索与文档查询</div>
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'auto', maxWidth: 900, margin: '0 auto', width: '100%', padding: 20, boxSizing: 'border-box' }}>
        <KnowledgePanel />
      </div>
    </div>
  )
}
