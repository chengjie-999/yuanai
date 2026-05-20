import { useState } from 'react'

const FEATURES: { key: string; label: string; icon: string; desc: string }[] = [
  { key: 'dataAnalysis', label: '数据分析', icon: '📊', desc: '数据看板和图表分析' },
  { key: 'datasets', label: '数据工作台', icon: '📂', desc: '上传和管理数据集' },
  { key: 'dataCollection', label: '数据采集', icon: '📡', desc: '网页内容抓取与保存' },
  { key: 'knowledge', label: '知识库', icon: '📚', desc: '管理思维导图知识库，支持私有/共享' },
  { key: 'tools', label: '工具面板', icon: '🔧', desc: '查看和在线执行工具' },
]

function getToggles(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem('featureToggles') || '{}')
  } catch { return {} }
}

function saveToggles(toggles: Record<string, boolean>) {
  localStorage.setItem('featureToggles', JSON.stringify(toggles))
}

export function useFeatureToggles(): [Record<string, boolean>, (key: string, v: boolean) => void] {
  const [toggles, setToggles] = useState<Record<string, boolean>>(() => {
    const saved = getToggles()
    // 默认开启
    for (const f of FEATURES) {
      if (saved[f.key] === undefined) saved[f.key] = true
    }
    return saved
  })

  const toggle = (key: string, v: boolean) => {
    const next = { ...toggles, [key]: v }
    setToggles(next)
    saveToggles(next)
  }

  return [toggles, toggle]
}

export default function SettingsPage({ toggles, onToggle }: { toggles: Record<string, boolean>; onToggle: (key: string, v: boolean) => void }) {
  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: '32px 20px' }}>
      <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 24, color: '#333' }}>⚙ 系统设置</h2>

      <div style={{ marginBottom: 32 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: '#999', marginBottom: 12 }}>功能开关</h3>
        {FEATURES.map((f) => (
          <div key={f.key} style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '14px 16px', borderRadius: 8, border: '1px solid #eee',
            marginBottom: 8, background: '#fff',
          }}>
            <span style={{ fontSize: 20 }}>{f.icon}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#333' }}>{f.label}</div>
              <div style={{ fontSize: 12, color: '#999' }}>{f.desc}</div>
            </div>
            <button onClick={() => onToggle(f.key, !toggles[f.key])}
              style={{
                padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
                background: toggles[f.key] ? '#4caf50' : '#e0e0e0',
                color: toggles[f.key] ? '#fff' : '#999',
                transition: 'all 0.15s',
              }}>
              {toggles[f.key] ? '已开启' : '已关闭'}
            </button>
          </div>
        ))}
      </div>

      <div style={{ fontSize: 13, color: '#999', background: '#f9f9f9', borderRadius: 8, padding: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>始终启用的功能</div>
        <div>💬 聊天</div>
      </div>
    </div>
  )
}
