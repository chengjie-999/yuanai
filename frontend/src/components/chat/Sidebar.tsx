import type { SessionInfo } from './helpers'
import { groupSessions } from './helpers'
import { PlusIcon, TrashIcon, PinIcon } from '../icons'

export default function Sidebar({ sessions, currentSid, sidebarOpen, isMobile, onNewSession, onSelect, onDelete }: {
  sessions: SessionInfo[]; currentSid: string; sidebarOpen: boolean; isMobile: boolean
  onNewSession: () => void; onSelect: (sid: string) => void; onDelete: (e: React.MouseEvent, sid: string) => void
}) {
  return (
    <div className={`chat-sidebar ${sidebarOpen ? 'sidebar-open' : ''}`} style={{
      width: isMobile ? 0 : (sidebarOpen ? 260 : 0),
      overflow: 'hidden',
      background: 'var(--sidebar-bg)', borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', flexShrink: 0,
      transition: isMobile ? 'left 0.25s ease' : 'width 0.2s',
    }}>
      <div style={{ padding: '12px 12px 8px', flexShrink: 0 }}>
        <button onClick={onNewSession} aria-label="新对话"
          style={{
            width: '100%', padding: '10px 0', borderRadius: 8,
            border: '1px solid var(--border)', background: 'var(--bg-input)',
            cursor: 'pointer', fontSize: 14, color: 'var(--text-primary)',
            transition: 'border-color 0.15s',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, lineHeight: 1,
          }}
        >
          <PlusIcon size={15} /> 新对话
        </button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px' }}>
        {groupSessions(sessions).map((group) => (
          <div key={group.label}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '12px 14px 4px', fontWeight: 600, letterSpacing: 0.5 }}>{group.label}</div>
            {group.items.map((s) => (
              <div key={s.session_id} onClick={() => onSelect(s.session_id)}
                style={{
                  padding: '9px 12px', borderRadius: 8, cursor: 'pointer', margin: '0 6px 2px',
                  background: currentSid === s.session_id ? 'var(--hover-bg)' : 'transparent',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  fontSize: 14, color: currentSid === s.session_id ? 'var(--text-primary)' : 'var(--text-secondary)',
                  transition: 'all 0.12s',
                }}
              >
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, display: 'flex', alignItems: 'center', gap: 4 }}>
                  {s.is_main && (
                    <span className="yuan-tip" data-tip="置顶主对话" aria-label="置顶主对话"
                      style={{ color: 'var(--accent)', display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                      <PinIcon size={11} />
                    </span>
                  )}
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {s.title.startsWith('🔧') ? <>{s.title}</> : s.title}
                  </span>
                </span>
                <span onClick={(e) => onDelete(e, s.session_id)} title="删除对话" aria-label="删除对话"
                  style={{ color: 'var(--text-muted)', cursor: 'pointer', padding: '2px 4px', flexShrink: 0, opacity: 0, transition: 'opacity 0.12s', display: 'flex', alignItems: 'center' }}
                  onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.color = 'var(--danger)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.opacity = '0'; e.currentTarget.style.color = 'var(--text-muted)' }}
                ><TrashIcon size={13} /></span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
