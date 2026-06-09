import { useState } from 'react'
import { Card, CardHeader } from './shared'

const row: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '14px 20px', borderBottom: '1px solid #f5f5f5', gap: 16,
}

const label: React.CSSProperties = { fontSize: 13, color: '#333', fontWeight: 500 }
const hint: React.CSSProperties = { fontSize: 11, color: '#bbb', marginTop: 2 }

const select: React.CSSProperties = {
  padding: '6px 10px', borderRadius: 6, border: '1px solid #ddd',
  fontSize: 13, outline: 'none', background: '#fff', minWidth: 140,
}

export default function SettingsTab() {
  const [logLevel, setLogLevel] = useState(localStorage.getItem('logLevel') || 'info')
  const [notifyError, setNotifyError] = useState(localStorage.getItem('notifyError') !== 'false')
  const [autoCollapse, setAutoCollapse] = useState(localStorage.getItem('autoCollapse') === 'true')

  const save = (key: string, value: string) => {
    localStorage.setItem(key, value)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Card>
        <CardHeader title="基本设置" />
        <div style={row}>
          <div>
            <div style={label}>日志级别</div>
            <div style={hint}>控制前端控制台日志详细程度</div>
          </div>
          <select
            value={logLevel}
            onChange={(e) => { setLogLevel(e.target.value); save('logLevel', e.target.value) }}
            style={select}
          >
            <option value="debug">Debug</option>
            <option value="info">Info</option>
            <option value="warn">Warn</option>
            <option value="error">Error</option>
          </select>
        </div>
        <div style={row}>
          <div>
            <div style={label}>错误通知</div>
            <div style={hint}>请求失败时在页面顶部显示通知</div>
          </div>
          <Toggle
            checked={notifyError}
            onChange={(v) => { setNotifyError(v); save('notifyError', String(v)) }}
          />
        </div>
        <div style={row}>
          <div>
            <div style={label}>自动收起侧栏</div>
            <div style={hint}>进入对话后自动收起工具栏侧栏</div>
          </div>
          <Toggle
            checked={autoCollapse}
            onChange={(v) => { setAutoCollapse(v); save('autoCollapse', String(v)) }}
          />
        </div>
      </Card>

      <Card>
        <CardHeader title="关于" />
        <div style={row}>
          <div style={label}>版本</div>
          <div style={{ fontSize: 13, color: '#666' }}>小元AI v2.0</div>
        </div>
        <div style={row}>
          <div style={label}>前端</div>
          <div style={{ fontSize: 12, color: '#999', fontFamily: 'monospace' }}>React 19 + TypeScript + Vite</div>
        </div>
        <div style={row}>
          <div style={label}>后端</div>
          <div style={{ fontSize: 12, color: '#999', fontFamily: 'monospace' }}>FastAPI + LangGraph + MySQL + Redis</div>
        </div>
      </Card>
    </div>
  )
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div
      onClick={() => onChange(!checked)}
      style={{
        width: 40, height: 22, borderRadius: 11,
        background: checked ? '#1976d2' : '#ccc',
        cursor: 'pointer', position: 'relative',
        transition: 'background 0.2s',
        flexShrink: 0,
      }}
    >
      <div style={{
        width: 18, height: 18, borderRadius: '50%', background: '#fff',
        position: 'absolute', top: 2,
        left: checked ? 20 : 2,
        transition: 'left 0.2s',
        boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
      }} />
    </div>
  )
}
