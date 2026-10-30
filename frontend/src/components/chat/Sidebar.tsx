import { useState } from 'react'
import type { SessionInfo } from './helpers'
import { groupSessions } from './helpers'
import { PlusIcon, TrashIcon, PinIcon, SearchIcon, EditIcon, ArchiveIcon } from '../icons'

export default function Sidebar({ sessions, currentSid, sidebarOpen, isMobile, onNewSession, onSelect, onDelete, onRename, onDemoteMain, onOpenTrash }: {
  sessions: SessionInfo[]; currentSid: string; sidebarOpen: boolean; isMobile: boolean
  onNewSession: () => void; onSelect: (sid: string) => void; onDelete: (e: React.MouseEvent, sid: string) => void
  onRename: (sid: string, title: string) => void
  onDemoteMain: (sid: string) => void
  onOpenTrash: () => void
}) {
  // U3 侧栏会话搜索（2026-10-25）：按标题客户端过滤
  const [query, setQuery] = useState('')
  const q = query.trim().toLowerCase()
  const filtered = q ? sessions.filter((s) => s.title.toLowerCase().includes(q)) : sessions

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
        <div style={{ position: 'relative', marginTop: 8 }}>
          <span style={{
            position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
            color: 'var(--text-muted)', display: 'flex', pointerEvents: 'none',
          }}><SearchIcon size={13} /></span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索会话"
            aria-label="搜索会话"
            style={{
              width: '100%', padding: '7px 10px 7px 30px', borderRadius: 8,
              border: '1px solid var(--border)', background: 'var(--bg-input)',
              fontSize: 13, outline: 'none', color: 'var(--text-primary)',
              boxSizing: 'border-box',
            }}
          />
        </div>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px' }}>
        {filtered.length === 0 && q && (
          <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '16px 14px', textAlign: 'center' }}>
            没有匹配「{query.trim()}」的会话
          </div>
        )}
        {groupSessions(filtered).map((group) => (
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
                <span style={{ display: 'flex', alignItems: 'center', gap: 2, flexShrink: 0 }}>
                  <span onClick={(e) => { e.stopPropagation(); onRename(s.session_id, s.title) }}
                    title="重命名" aria-label="重命名"
                    className="yuan-tip" data-tip="重命名"
                    style={{ color: 'var(--text-muted)', cursor: 'pointer', padding: '2px 4px', display: 'flex', alignItems: 'center' }}
                    onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--accent)' }}
                    onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
                  ><EditIcon size={13} /></span>
                  {/* 主对话降级（2026-10-30）：不清数据——转普通对话 + 自动新建空主对话 */}
                  {s.is_main && (
                    <span onClick={(e) => { e.stopPropagation(); onDemoteMain(s.session_id) }}
                      title="转为普通对话" aria-label="转为普通对话"
                      className="yuan-tip" data-tip="转为普通对话（保留全部历史，自动新建空主对话）"
                      style={{ color: 'var(--text-muted)', cursor: 'pointer', padding: '2px 4px', display: 'flex', alignItems: 'center' }}
                      onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--accent)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
                    ><ArchiveIcon size={13} /></span>
                  )}
                  {/* 主对话不可删除（2026-10-30 修复）：删除后当前页继续发消息会落孤儿数据，
                      刷新又自动重建——主对话是每用户唯一锚点，隐藏删除按钮 */}
                  {!s.is_main && (
                    <span onClick={(e) => onDelete(e, s.session_id)} title="删除对话" aria-label="删除对话"
                      className="chat-session-del"
                      style={{ color: 'var(--text-muted)', cursor: 'pointer', padding: '2px 4px', display: 'flex', alignItems: 'center' }}
                      onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--danger)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
                    ><TrashIcon size={13} /></span>
                  )}
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>
      {/* 回收站入口（2026-10-31 用户拍板：侧边栏最底端） */}
      <div style={{ padding: '8px 12px 14px', borderTop: '1px solid var(--border-light)', flexShrink: 0 }}>
        <button onClick={onOpenTrash} aria-label="回收站"
          className="yuan-tip" data-tip="回收站（已删除的对话可恢复）"
          style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4, padding: '4px 8px', width: '100%' }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-secondary)' }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}>
          <TrashIcon size={13} /> 回收站
        </button>
      </div>
    </div>
  )
}
