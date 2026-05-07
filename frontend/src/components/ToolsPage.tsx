import { useState, useEffect } from 'react'
import { fetchTools, API_BASE, getToken, getStoredUser } from '../api'
import type { ToolInfo } from '../types'

const CATEGORY_ICONS: Record<string, string> = {
  '计算': '🧮', '天气': '🌤', '审核': '🎯',
  '浏览器': '🌐', '小猿任务': '📋', '监控': '📺', '文件': '📁', 'Cookie': '🍪',
  '系统': '🤖', '其他': '📦',
}

const CATEGORY_COLORS: Record<string, string> = {
  '计算': '#e3f2fd', '天气': '#fff3e0', '审核': '#f3e5f5',
  '浏览器': '#e8f5e9', '小猿任务': '#fce4ec', '监控': '#e0f7fa',
  '文件': '#eef6e6', 'Cookie': '#fff8e1', '系统': '#f5f5f5', '其他': '#f5f5f5',
}

function ToolExecutor({ tool, disabled }: { tool: ToolInfo; disabled: boolean }) {
  const [args, setArgs] = useState<Record<string, string>>({})
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [executing, setExecuting] = useState(false)

  const properties = (tool.args as any)?.properties || {}
  const required = (tool.args as any)?.required || []

  const handleExecute = async () => {
    if (disabled) return
    setExecuting(true)
    setResult(null)
    setError(null)
    try {
      const parsed: Record<string, any> = {}
      for (const [key, val] of Object.entries(args)) {
        const prop = properties[key]
        if (prop?.type === 'number' || prop?.type === 'integer') {
          parsed[key] = Number(val)
        } else if (prop?.type === 'boolean') {
          parsed[key] = val === 'true'
        } else {
          parsed[key] = val
        }
      }
      const token = getToken()
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      const res = await fetch(`${API_BASE}/tools/execute`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ name: tool.name, args: parsed }),
      })
      if (!res.ok) {
        const err = await res.text()
        setError(err)
      } else {
        const data = await res.json()
        setResult(data.result)
      }
    } catch (e: any) {
      setError(String(e))
    }
    setExecuting(false)
  }

  const hasArgs = Object.keys(properties).length > 0

  return (
    <div style={{ marginTop: 8, borderTop: '1px solid #eee', paddingTop: 8 }}>
      {hasArgs && (
        <div style={{ marginBottom: 8 }}>
          {Object.entries(properties).map(([key, prop]: any) => (
            <div key={key} style={{ marginBottom: 6 }}>
              <label style={{ display: 'block', fontSize: 12, color: '#666', marginBottom: 2 }}>
                {key} {required.includes(key) ? <span style={{ color: 'red' }}>*</span> : ''}
                <span style={{ color: '#999', marginLeft: 4 }}>({prop.type || 'string'})</span>
              </label>
              <input
                value={args[key] || ''}
                onChange={(e) => setArgs((p) => ({ ...p, [key]: e.target.value }))}
                placeholder={prop.description || key}
                style={{
                  width: '100%', padding: '6px 8px', borderRadius: 4,
                  border: '1px solid #ccc', fontSize: 13, boxSizing: 'border-box',
                }}
              />
            </div>
          ))}
        </div>
      )}
      <button
        onClick={handleExecute}
        disabled={executing || disabled}
        style={{
          padding: '6px 16px', borderRadius: 4, border: 'none',
          background: executing || disabled ? '#ccc' : '#1976d2', color: '#fff',
          cursor: executing || disabled ? 'not-allowed' : 'pointer', fontSize: 13,
        }}
      >
        {disabled ? '仅管理员' : (executing ? '执行中...' : (hasArgs ? '执行' : '运行'))}
      </button>
      {result !== null && (
        <div style={{
          marginTop: 8, padding: 8, background: '#f0faf0', borderRadius: 4,
          fontSize: 13, color: '#333', whiteSpace: 'pre-wrap',
          maxHeight: 200, overflow: 'auto',
        }}>
          {result}
        </div>
      )}
      {error && (
        <div style={{
          marginTop: 8, padding: 8, background: '#fff0f0', borderRadius: 4,
          fontSize: 13, color: '#c00',
        }}>
          ❌ {error}
        </div>
      )}
    </div>
  )
}

function ToolCard({ tool, disabled }: { tool: ToolInfo; disabled: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{
      marginBottom: 4, borderRadius: 8, border: '1px solid #eee',
      overflow: 'hidden', background: '#fff', opacity: disabled ? 0.5 : 1,
    }}>
      <div
        onClick={() => !disabled && setOpen(!open)}
        style={{
          padding: '8px 12px', cursor: disabled ? 'not-allowed' : 'pointer', display: 'flex',
          alignItems: 'center', gap: 8, fontSize: 13,
          transition: 'background 0.1s',
        }}
        onMouseEnter={(e) => { if (!disabled) e.currentTarget.style.background = '#fafafa' }}
        onMouseLeave={(e) => { e.currentTarget.style.background = '#fff' }}
      >
        <code style={{ fontWeight: 600, color: disabled ? '#999' : '#333', fontSize: 13 }}>{tool.name}</code>
        <span style={{ color: disabled ? '#ccc' : '#999', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>
          {tool.description}
        </span>
        {disabled && <span style={{ fontSize: 10, color: '#bbb', background: '#f5f5f5', padding: '1px 6px', borderRadius: 4 }}>admin</span>}
        {!disabled && <span style={{ color: '#bbb', fontSize: 11, flexShrink: 0 }}>
          {open ? '收起' : '展开'}
        </span>}
      </div>
      {open && !disabled && (
        <div style={{ padding: '0 12px 12px' }}>
          <ToolExecutor tool={tool} disabled={false} />
        </div>
      )}
    </div>
  )
}

export default function ToolsPage() {
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})

  const user = getStoredUser()
  const isAdmin = user?.role === 'admin'

  useEffect(() => {
    fetchTools()
      .then((data) => setTools(data))
      .catch((e) => console.error(e))
      .finally(() => setLoading(false))
  }, [])

  const grouped: Record<string, ToolInfo[]> = {}
  for (const t of tools) {
    const cat = t.category || '其他'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push(t)
  }

  const allMatch = (tool: ToolInfo) =>
    tool.name.toLowerCase().includes(search.toLowerCase()) ||
    tool.description.toLowerCase().includes(search.toLowerCase())

  const hasSearch = search.trim().length > 0

  const categoryOrder = ['计算', '天气', '审核', '浏览器', '小猿任务', '监控', '系统', '文件', 'Cookie', '其他']
  const sortedCats = Object.keys(grouped).sort(
    (a, b) => categoryOrder.indexOf(a) - categoryOrder.indexOf(b)
  )

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: 20, height: '100%', overflowY: 'auto' }}>
      <h2 style={{ marginBottom: 16, fontSize: 18, fontWeight: 600 }}>
        工具面板
        <span style={{ fontSize: 14, color: '#999', fontWeight: 400, marginLeft: 8 }}>
          {tools.length} 个工具 · {Object.keys(grouped).length} 类
          {!isAdmin && <span style={{ fontSize: 12, color: '#ccc', marginLeft: 8 }}>（灰显为仅管理员）</span>}
        </span>
      </h2>

      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="搜索工具名称或描述..."
        style={{
          width: '100%', padding: '10px 14px', borderRadius: 8,
          border: '1px solid #ddd', fontSize: 14, outline: 'none',
          marginBottom: 16, boxSizing: 'border-box',
        }}
        onFocus={(e) => (e.target.style.borderColor = '#1976d2')}
        onBlur={(e) => (e.target.style.borderColor = '#ddd')}
      />

      {loading && <div style={{ color: '#999', padding: 20, textAlign: 'center' }}>加载中...</div>}

      {!loading && sortedCats.map((cat) => {
        const filtered = grouped[cat].filter((t) => hasSearch ? allMatch(t) : true)
        if (filtered.length === 0 && !hasSearch) return null
        const isCollapsed = collapsed[cat]
        const icon = CATEGORY_ICONS[cat] || '📦'
        const color = CATEGORY_COLORS[cat] || '#f5f5f5'

        return (
          <div key={cat} style={{ marginBottom: 12 }}>
            <div
              onClick={() => setCollapsed((p) => ({ ...p, [cat]: !isCollapsed }))}
              style={{
                padding: '10px 14px', borderRadius: 8, cursor: 'pointer',
                background: color, display: 'flex', alignItems: 'center', gap: 8,
                marginBottom: 6,
              }}
            >
              <span style={{ fontSize: 16 }}>{icon}</span>
              <span style={{ fontWeight: 600, fontSize: 14, color: '#333', flex: 1 }}>
                {cat}
              </span>
              <span style={{ fontSize: 12, color: '#999' }}>
                {hasSearch ? `${filtered.length}/${grouped[cat].length}` : grouped[cat].length}
              </span>
              <span style={{ fontSize: 11, color: '#bbb', transition: 'transform 0.15s', transform: isCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }}>
                ▼
              </span>
            </div>
            {!isCollapsed && filtered.map((tool) => (
              <ToolCard key={tool.name} tool={tool} disabled={!!(tool.admin_only && !isAdmin)} />
            ))}
          </div>
        )
      })}
    </div>
  )
}
