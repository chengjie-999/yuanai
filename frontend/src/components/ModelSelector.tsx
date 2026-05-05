import { useState, useEffect, useRef } from 'react'

export const MODELS = [
  { value: 'doubao-seed-2-0-pro-260215', label: '豆包 Pro', provider: 'Doubao' },
  { value: 'doubao-seed-2-0-lite-260215', label: '豆包 Lite', provider: 'Doubao' },
  { value: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash', provider: 'DeepSeek' },
  { value: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro', provider: 'DeepSeek' },
]

export function ModelSelector({ model, onChange }: { model: string; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false)
  const [upward, setUpward] = useState(false)
  const current = MODELS.find((m) => m.value === model) || MODELS[0]
  const ref = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const toggle = () => {
    if (!open) {
      setOpen(true)
      setTimeout(() => {
        if (menuRef.current && ref.current) {
          const rect = ref.current.getBoundingClientRect()
          const spaceBelow = window.innerHeight - rect.bottom - 8
          setUpward(spaceBelow < 240)
        }
      }, 0)
    } else {
      setOpen(false)
    }
  }

  const provider = current.provider
  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={toggle} style={{
        padding: '6px 12px', borderRadius: 8, border: '1px solid #e5e5e5',
        background: '#fff', cursor: 'pointer', fontSize: 13, color: '#333',
        display: 'flex', alignItems: 'center', gap: 6,
      }} onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#bbb')}
        onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#e5e5e5')}>
        <span style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: provider === 'Doubao' ? '#10a37f' : '#6366f1' }} />
        <span style={{ fontSize: 13 }}>{current.label}</span>
        <span style={{ fontSize: 9, color: '#bbb', marginLeft: 2 }}>▼</span>
      </button>
      {open && (
        <div ref={menuRef} style={{
          position: 'absolute', [upward ? 'bottom' : 'top']: '100%',
          [upward ? 'marginBottom' : 'marginTop']: 4, left: 0,
          background: '#fff', borderRadius: 10, border: '1px solid #e5e5e5',
          boxShadow: '0 4px 24px rgba(0,0,0,0.1)', padding: 6, zIndex: 100, minWidth: 210,
        }}>
          {['Doubao', 'DeepSeek'].map((p) => (
            <div key={p}>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#999', padding: '4px 8px', marginTop: 4, letterSpacing: 0.5, textTransform: 'uppercase' }}>{p}</div>
              {MODELS.filter((m) => m.provider === p).map((m) => (
                <div key={m.value} onClick={() => { onChange(m.value); setOpen(false) }}
                  style={{ padding: '8px 10px', borderRadius: 6, cursor: 'pointer', background: model === m.value ? '#f5f5f5' : 'transparent', display: 'flex', alignItems: 'center', gap: 10 }}
                  onMouseEnter={(e) => { if (model !== m.value) e.currentTarget.style.background = '#fafafa' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = model === m.value ? '#f5f5f5' : 'transparent' }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: p === 'Doubao' ? '#10a37f' : '#6366f1' }} />
                  <div style={{ flex: 1 }}><div style={{ fontSize: 14, color: '#333' }}>{m.label}</div></div>
                  {model === m.value && <span style={{ color: '#10a37f', fontSize: 14 }}>✓</span>}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
