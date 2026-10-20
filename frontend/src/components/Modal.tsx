import { useEffect } from 'react'
import type { ReactNode } from 'react'
import { XIcon } from './icons'

/* 共享遮罩弹层（2026-10-21 清洁6）：各页面自写遮罩（8 处）收敛为一处
   mode=center 居中卡片（默认）/ right 右侧抽屉；Esc 与遮罩点击关闭统一 */
export default function Modal({ open, onClose, title, children, footer, mode = 'center', width }: {
  open: boolean
  onClose: () => void
  title?: string
  children: ReactNode
  footer?: ReactNode
  mode?: 'center' | 'right'
  width?: number
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  if (mode === 'right') {
    return (
      <>
        <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', zIndex: 9998 }} />
        <div style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: width || 420, maxWidth: '90vw',
          background: 'var(--bg-primary)', zIndex: 9999, boxShadow: '-4px 0 24px rgba(0,0,0,0.12)',
          display: 'flex', flexDirection: 'column', animation: 'slide-in-right 0.25s ease' }}>
          {title !== undefined && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '20px 24px', borderBottom: '1px solid var(--border)' }}>
              <h2 style={{ fontSize: 17, fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>{title}</h2>
              <button onClick={onClose} title="关闭" aria-label="关闭"
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '4px', lineHeight: 1, display: 'flex' }}>
                <XIcon size={16} />
              </button>
            </div>
          )}
          <div style={{ flex: 1, overflow: 'auto', padding: '24px' }}>{children}</div>
          {footer && (
            <div style={{ padding: '16px 24px', borderTop: '1px solid var(--border)', display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              {footer}
            </div>
          )}
        </div>
      </>
    )
  }

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: 'var(--bg-primary)', borderRadius: 12, padding: 24, minWidth: 380, maxWidth: '92vw', maxHeight: '86vh', overflow: 'auto', boxShadow: '0 8px 40px var(--shadow-md)' }}>
        {title !== undefined && <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</h3>}
        {children}
      </div>
    </div>
  )
}
