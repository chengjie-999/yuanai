import type { SessionInfo } from './helpers'
import { groupSessions } from './helpers'

export default function Sidebar({ sessions, currentSid, sidebarOpen, onNewSession, onSelect, onDelete }: {
  sessions: SessionInfo[]; currentSid: string; sidebarOpen: boolean
  onNewSession: () => void; onSelect: (sid: string) => void; onDelete: (e: React.MouseEvent, sid: string) => void
}) {
  return (
    <div style={{
      width: sidebarOpen ? 260 : 0, overflow: 'hidden',
      background: '#f8f9fb', borderRight: '1px solid #e8e8ec',
      display: 'flex', flexDirection: 'column', flexShrink: 0,
      transition: 'width 0.2s',
    }}>
      <div style={{ padding: '12px 12px 8px', flexShrink: 0 }}>
        <button onClick={onNewSession}
          style={{
            width: '100%', padding: '10px 0', borderRadius: 8,
            border: '1px solid #d0d0d0', background: '#fff',
            cursor: 'pointer', fontSize: 14, color: '#333',
            transition: 'border-color 0.15s',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#999')}
          onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#d0d0d0')}
        >
          + 新对话
        </button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px' }}>
        {groupSessions(sessions).map((group) => (
          <div key={group.label}>
            <div style={{ fontSize: 11, color: '#b0b8c8', padding: '12px 14px 4px', fontWeight: 600, letterSpacing: 0.5 }}>{group.label}</div>
            {group.items.map((s) => (
              <div key={s.session_id} onClick={() => onSelect(s.session_id)}
                style={{
                  padding: '9px 12px', borderRadius: 8, cursor: 'pointer', margin: '0 6px 2px',
                  background: currentSid === s.session_id ? '#eef0f5' : 'transparent',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  fontSize: 14, color: currentSid === s.session_id ? '#1a1a2e' : '#444',
                  transition: 'all 0.12s',
                }}
                onMouseEnter={(e) => { if (currentSid !== s.session_id) e.currentTarget.style.background = '#f0f0f4' }}
                onMouseLeave={(e) => { e.currentTarget.style.background = currentSid === s.session_id ? '#eef0f5' : 'transparent' }}
              >
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                  {s.title.startsWith('🔧') ? <>{s.title}</> : s.title}
                </span>
                <span onClick={(e) => onDelete(e, s.session_id)}
                  style={{ color: '#bbb', cursor: 'pointer', padding: '2px 4px', fontSize: 13, flexShrink: 0, opacity: 0, transition: 'opacity 0.12s' }}
                  onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                  onMouseLeave={(e) => (e.currentTarget.style.opacity = '0')}
                >✕</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
