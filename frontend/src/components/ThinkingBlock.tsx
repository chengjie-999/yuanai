import { useState } from 'react'

export default function ThinkingBlock({ content }: { content: string }) {
  const [open, setOpen] = useState(false)
  if (!content) return null

  return (
    <div style={{
      margin: '8px 0',
      borderRadius: 10,
      border: '1px solid var(--border)',
      overflow: 'hidden',
      fontSize: 13,
      background: 'var(--bg-tertiary)',
    }}>
      <div
        onClick={() => setOpen(!open)}
        style={{
          padding: '8px 14px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: 'var(--text-secondary)',
          userSelect: 'none',
          transition: 'background 0.15s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--hover-bg)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        <span style={{ fontSize: 15, lineHeight: 1 }}>💭</span>
        <span style={{ flex: 1, fontWeight: 600, fontSize: 13, color: 'var(--text-secondary)' }}>
          思考过程
        </span>
        <span style={{
          fontSize: 10,
          color: 'var(--text-muted)',
          transition: 'transform 0.25s',
          transform: open ? 'rotate(180deg)' : 'none',
        }}>
          ▼
        </span>
      </div>
      {open && (
        <div style={{
          padding: '10px 14px',
          background: 'var(--bg-secondary)',
          color: 'var(--text-secondary)',
          lineHeight: 1.7,
          whiteSpace: 'pre-wrap',
          borderTop: '1px solid var(--border)',
          fontSize: 13,
          fontStyle: 'italic',
        }}>
          {content}
        </div>
      )}
    </div>
  )
}
