import { useEffect, useState } from 'react'
import { API_BASE, authHeaders } from '../api'
import { MegaphoneIcon, XIcon } from './icons'
import Modal from './Modal'

/* 更新公告（2026-10-31 用户拍板：网站部署更新与本地 Agent 更新各发一条公告）

显示设计：顶栏下方细横幅展示「最新未读」一条（喇叭图标 + 标题 + 详情/关闭）；
「详情」打开面板列出全部公告；已读状态 localStorage 记忆（readAnnouncements）。
公告来源：部署自动公告（site）/ Agent 版本自动公告（agent）/ 管理员手动。 */

type Ann = { id: string; title: string; content: string; kind: string; version: string; created_at: string }

const READ_KEY = 'readAnnouncements'

function _readIds(): string[] {
  try { return JSON.parse(localStorage.getItem(READ_KEY) || '[]') } catch { return [] }
}
function _saveReadIds(ids: string[]) {
  try { localStorage.setItem(READ_KEY, JSON.stringify(ids)) } catch { /* 忽略 */ }
}

export default function AnnouncementBar() {
  const [all, setAll] = useState<Ann[]>([])
  const [read, setRead] = useState<string[]>(_readIds())
  const [open, setOpen] = useState(false)

  useEffect(() => {
    fetch(`${API_BASE}/announcements?limit=20`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : []))
      .then(setAll)
      .catch(() => {})
  }, [])

  const unread = all.find((a) => !read.includes(a.id))
  if (!unread) return null

  // 关闭 = 全部已读（2026-10-31 用户拍板：不要一条条点——当前已加载的公告一次全关，
  // 之后新发布的公告会再次出现）
  const markAllRead = () => {
    const next = [...new Set([...read, ...all.map((a) => a.id)])]
    setRead(next)
    _saveReadIds(next)
  }

  return (
    <>
      {/* 细横幅：最新未读公告 */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
        padding: '5px 14px', background: 'var(--accent-soft)',
        borderBottom: '1px solid var(--border-light)', fontSize: 12.5,
        color: 'var(--text-secondary)',
      }}>
        <span style={{ color: 'var(--accent)', display: 'flex', flexShrink: 0 }}><MegaphoneIcon size={14} /></span>
        <span style={{ color: 'var(--text-primary)', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {unread.title}
        </span>
        <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--text-muted)' }}>
          {unread.content}
        </span>
        <button onClick={() => setOpen(true)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: 'var(--accent)', flexShrink: 0, padding: 0 }}>
          详情
        </button>
        <button onClick={markAllRead} title="全部关闭" aria-label="全部关闭"
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 2, display: 'flex', lineHeight: 1, flexShrink: 0 }}>
          <XIcon size={13} />
        </button>
      </div>

      {/* 全部公告面板 */}
      {open && (
        <Modal open title="更新公告" onClose={() => setOpen(false)}>
          <div style={{ minWidth: 400, maxWidth: 480 }}>
            <div style={{ maxHeight: 340, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
              {all.length === 0 ? (
                <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>暂无公告</div>
              ) : all.map((a) => (
                <div key={a.id} style={{ padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border-light)', background: 'var(--bg-secondary)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <span style={{ fontSize: 11, color: '#fff', padding: '1px 8px', borderRadius: 999,
                      background: a.kind === 'agent' ? 'var(--success)' : 'var(--accent)', flexShrink: 0 }}>
                      {a.kind === 'agent' ? '电脑端更新' : '网站更新'}
                    </span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{a.title}</span>
                    <div style={{ flex: 1 }} />
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>{a.created_at?.slice(0, 16)}</span>
                  </div>
                  <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.7 }}>{a.content}</div>
                </div>
              ))}
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}
