import { createPortal } from 'react-dom'

/** 移动端长按底部 sheet 菜单（T14 P1-1 从 MessageBubble 抽出，2026-11-18 起
    BlockLongPress 块级菜单复用）：复用 voiceSheetIn 入场动画，
    操作项与桌面操作行一一对应。 */
export default function MobileSheetMenu({ items, onClose }: {
  items: { label: string; onClick: () => void; danger?: boolean; disabled?: boolean }[]
  onClose: () => void
}) {
  return createPortal(
    <div onClick={onClose} style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9600,
      display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
      background: 'rgba(15,23,42,0.4)',
    }}>
      <div onClick={(e) => e.stopPropagation()} className="voice-sheet" style={{
        width: '100%', maxWidth: 560, borderRadius: '16px 16px 0 0',
        background: 'var(--bg-primary)',
        padding: '4px 12px calc(12px + var(--safe-bottom, 0px))',
        boxShadow: '0 12px 40px var(--shadow-md)',
      }}>
        {items.map((it) => (
          <button key={it.label} disabled={it.disabled}
            onClick={() => { it.onClick(); onClose() }}
            style={{
              display: 'block', width: '100%', textAlign: 'left', border: 'none',
              background: 'none', cursor: it.disabled ? 'default' : 'pointer',
              padding: '14px 8px', fontSize: 15, borderBottom: '1px solid var(--border-light)',
              color: it.danger ? 'var(--danger)' : 'var(--text-primary)',
              opacity: it.disabled ? 0.4 : 1,
            }}>
            {it.label}
          </button>
        ))}
        <button onClick={onClose}
          style={{
            display: 'block', width: '100%', textAlign: 'center', border: 'none',
            background: 'none', cursor: 'pointer', padding: '14px 8px', fontSize: 15,
            color: 'var(--text-muted)', marginTop: 2,
          }}>
          取消
        </button>
      </div>
    </div>,
    document.body,
  )
}
