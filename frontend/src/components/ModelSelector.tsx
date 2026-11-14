import { useState, useEffect, useRef } from 'react'
import { API_BASE, headers } from '../api'

type ModelInfo = { value: string; label: string; provider: string }

const FALLBACK_MODELS: ModelInfo[] = [
  { value: 'doubao-seed-2-0-pro-260215', label: '豆包 Pro', provider: 'Doubao' },
  { value: 'doubao-seed-2-0-lite-260215', label: '豆包 Lite', provider: 'Doubao' },
  { value: 'deepseek-flash', label: 'DeepSeek V4.1 Flash', provider: 'DeepSeek' },
  { value: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro', provider: 'DeepSeek' },
]

function useModels(): ModelInfo[] {
  const [models, setModels] = useState<ModelInfo[]>(FALLBACK_MODELS)
  useEffect(() => {
    fetch(`${API_BASE}/admin/models`, { headers: headers() })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data && typeof data === 'object' && !Array.isArray(data)) {
          const list = Object.entries(data).map(([id, info]: [string, any]) => ({
            value: id,
            label: info?.label || id,
            provider: info?.provider || 'Custom',
          }))
          if (list.length > 0) setModels(list)
        }
      })
      .catch(() => {}) // 回退到硬编码列表
  }, [])
  return models
}

export function ModelSelector({ model, onChange }: { model: string; onChange: (v: string) => void }) {
  const models = useModels()
  const [open, setOpen] = useState(false)
  const [upward, setUpward] = useState(false)
  const current = models.find((m) => m.value === model) || models[0]
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
      {/* 2026-11-14 用户拍板：按钮只显简称（全 ID 进悬浮提示）——此前 ID 副显
          又长又丑，且弹层内嵌套下拉像「二级子页面」 */}
      <button onClick={toggle} aria-label={`选择模型: ${current.label}`} title={`${current.label}（${current.value}）`} style={{
        padding: '4px 10px', borderRadius: 999, border: '1px solid var(--border)',
        background: 'var(--bg-input)', cursor: 'pointer', color: 'var(--text-primary)',
        display: 'flex', alignItems: 'center', gap: 5, fontSize: 12,
      }} onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--text-secondary)')}
        onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', flexShrink: 0, background: provider === 'Doubao' ? '#10a37f' : '#6366f1' }} />
        <span style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{current.label}</span>
      </button>
      {open && (
        <div ref={menuRef} style={{
          position: 'absolute', [upward ? 'bottom' : 'top']: '100%',
          [upward ? 'marginBottom' : 'marginTop']: 4, left: 0,
          background: 'var(--bg-primary)', borderRadius: 10, border: '1px solid var(--border)',
          boxShadow: '0 4px 24px var(--shadow-md)', padding: 6, zIndex: 100, minWidth: 300,
        }}>
          {[...new Set(models.map(m => m.provider))].map((p) => (
            <div key={p}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', padding: '4px 8px', marginTop: 4, letterSpacing: 0.5, textTransform: 'uppercase' }}>{p}</div>
              {models.filter((m) => m.provider === p).map((m) => (
                <div key={m.value} onClick={() => { onChange(m.value); setOpen(false) }}
                  style={{ padding: '8px 10px', borderRadius: 6, cursor: 'pointer', background: model === m.value ? 'var(--hover-bg)' : 'transparent', display: 'flex', alignItems: 'center', gap: 10 }}
                >
                  <span style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: p === 'Doubao' ? '#10a37f' : '#6366f1' }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{m.label}</div>
                    <div style={{ fontSize: 10, fontFamily: 'monospace', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.value}</div>
                  </div>
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
