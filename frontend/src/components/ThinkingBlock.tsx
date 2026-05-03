import { useState } from 'react'

export default function ThinkingBlock({ content }: { content: string }) {
  const [open, setOpen] = useState(false)
  if (!content) return null

  return (
    <div style={{
      margin: '8px 0',
      borderRadius: 10,
      border: '1px solid #e8e0d0',
      overflow: 'hidden',
      fontSize: 13,
      background: '#fcf9f2',
    }}>
      <div
        onClick={() => setOpen(!open)}
        style={{
          padding: '8px 14px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: '#8b7d6b',
          userSelect: 'none',
          transition: 'background 0.15s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = '#f8f3ea')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        <span style={{ fontSize: 15, lineHeight: 1 }}>💭</span>
        <span style={{ flex: 1, fontWeight: 600, fontSize: 13, color: '#8b7d6b' }}>
          思考过程
        </span>
        <span style={{
          fontSize: 10,
          color: '#c0b4a4',
          transition: 'transform 0.25s',
          transform: open ? 'rotate(180deg)' : 'none',
        }}>
          ▼
        </span>
      </div>
      {open && (
        <div style={{
          padding: '10px 14px',
          background: '#fefcf8',
          color: '#6b5d4d',
          lineHeight: 1.7,
          whiteSpace: 'pre-wrap',
          borderTop: '1px solid #e8e0d0',
          fontSize: 13,
          fontStyle: 'italic',
        }}>
          {content}
        </div>
      )}
    </div>
  )
}
