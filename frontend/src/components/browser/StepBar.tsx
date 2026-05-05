import { useState } from 'react'
import type { Step } from './helpers'
import { STEPS } from './helpers'

export default function StepBar({ step, onStep, onReset, taskName }: { step: Step; onStep: (s: Step) => void; onReset: () => void; taskName?: string }) {
  const [hovered, setHovered] = useState<number | null>(null)

  const getDesc = (s: typeof STEPS[0]) => {
    if (s.n === 3 && taskName) return `${taskName} 正在执行中`
    return s.desc
  }

  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
      {STEPS.map((s) => {
        const active = step === s.n
        const done = s.n < step
        const showDesc = hovered === s.n
        return (
          <div key={s.n} onClick={() => onStep(s.n)}
            onMouseEnter={() => setHovered(s.n)} onMouseLeave={() => setHovered(null)}
            style={{
              flex: 1, padding: '6px 12px', borderRadius: 6, cursor: 'pointer',
              background: active ? '#1976d2' : done ? '#e8f5e9' : '#f5f5f5',
              border: active ? '2px solid #1976d2' : done ? '2px solid #4caf50' : '2px solid #e0e0e0',
              transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 8,
              height: showDesc ? 48 : 32, overflow: 'hidden',
            }}>
            <span style={{
              width: 22, height: 22, borderRadius: '50%', display: 'flex', alignItems: 'center',
              justifyContent: 'center', flexShrink: 0,
              background: active ? '#fff' : done ? '#4caf50' : '#e0e0e0',
              color: active ? '#1976d2' : '#fff', fontWeight: 700, fontSize: 12,
            }}>{done ? '✓' : s.n}</span>
            <span style={{ fontWeight: 600, fontSize: 13, color: active ? '#fff' : done ? '#2e7d32' : '#999', whiteSpace: 'nowrap' }}>
              {s.label}
            </span>
            {showDesc && (
              <span style={{ fontSize: 11, color: active ? 'rgba(255,255,255,0.8)' : done ? '#66bb6a' : '#bbb', marginLeft: 4, whiteSpace: 'nowrap' }}>
                {getDesc(s)}
              </span>
            )}
          </div>
        )
      })}
      <button onClick={onReset} style={{
        padding: '4px 10px', borderRadius: 6, border: '1px solid #e0e0e0',
        background: '#fff', cursor: 'pointer', fontSize: 11, color: '#999', flexShrink: 0,
      }}>↺</button>
    </div>
  )
}
