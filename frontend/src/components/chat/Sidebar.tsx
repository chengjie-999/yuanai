import type { SessionInfo } from './helpers'

export default function Sidebar({ sessions, currentSid, sidebarOpen, onNewSession, onSelect, onDelete, onToggle }: {
  sessions: SessionInfo[]; currentSid: string; sidebarOpen: boolean
  onNewSession: () => void; onSelect: (sid: string) => void; onDelete: (e: React.MouseEvent, sid: string) => void; onToggle: () => void
}) {
  return (
    <div style={{
      width: sidebarOpen ? 260 : 0, overflow: 'hidden', background: '#f7f7f8',
      borderRight: '1px solid #e5e5e5', display: 'flex', flexDirection: 'column', flexShrink: 0,
      transition: 'width 0.2s',
    }}>
      <div style={{ padding: 12, flexShrink: 0 }}>
        <button onClick={onNewSession} style={{
          width: '100%', padding: '10px 0', borderRadius: 8, border: '1px solid #d0d0d0',
          background: '#fff', cursor: 'pointer', fontSize: 14, color: '#333',
        }} onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#999')}
          onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#d0d0d0')}>+ 新对话</button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px' }}>
        {sessions.map((s) => (
          <div key={s.session_id} onClick={() => onSelect(s.session_id)}
            style={{
              padding: '10px 12px', borderRadius: 8, cursor: 'pointer', marginBottom: 2,
              background: currentSid === s.session_id ? '#e8e8ea' : 'transparent',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              fontSize: 14, color: '#333', transition: 'background 0.1s',
            }}
            onMouseEnter={(e) => { if (currentSid !== s.session_id) e.currentTarget.style.background = '#f0f0f0' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = currentSid === s.session_id ? '#e8e8ea' : 'transparent' }}>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, display: 'flex', alignItems: 'center', gap: 6 }}>
              {(s as any).is_special || s.title === '自动化' ? <span style={{ fontSize: 13 }}>📌</span> : null}
              {s.title}
            </span>
            {(s as any).is_special || s.title === '自动化' ? (
              <span style={{ fontSize: 11, color: '#ccc', padding: '2px 4px', flexShrink: 0 }}>🔒</span>
            ) : (
              <span onClick={(e) => onDelete(e, s.session_id)} style={{
                color: '#bbb', cursor: 'pointer', padding: '2px 4px', fontSize: 13, flexShrink: 0,
                opacity: 0.3, transition: 'opacity 0.15s',
              }} onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.3')}>✕</span>
            )}
          </div>
        ))}
      </div>
      <div style={{ padding: '8px 12px', borderTop: '1px solid #e5e5e5', flexShrink: 0 }}>
        <button onClick={onToggle} style={{ background: 'none', border: 'none', color: '#999', cursor: 'pointer', fontSize: 13, padding: 0 }}>◀ 收起</button>
      </div>
    </div>
  )
}
