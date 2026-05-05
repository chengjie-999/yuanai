import { useState, useEffect } from 'react'
import { fetchTools, API_BASE } from '../api'
import type { ToolInfo } from '../types'

const CATEGORY_ICONS: Record<string, string> = {
  '计算': '🧮', '天气': '🌤', '审核': '🎯',
  '浏览器': '🌐', '小猿任务': '📋', '其他': '📦',
}

const CATEGORY_COLORS: Record<string, string> = {
  '计算': '#e3f2fd', '天气': '#fff3e0', '审核': '#f3e5f5',
  '浏览器': '#e8f5e9', '小猿任务': '#fce4ec', '其他': '#f5f5f5',
}

function ToolExecutor({ tool }: { tool: ToolInfo }) {
  const [args, setArgs] = useState<Record<string, string>>({})
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [executing, setExecuting] = useState(false)

  const properties = (tool.args as any)?.properties || {}
  const required = (tool.args as any)?.required || []

  const handleExecute = async () => {
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
      const res = await fetch(`${API_BASE}/tools/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
        disabled={executing}
        style={{
          padding: '6px 16px', borderRadius: 4, border: 'none',
          background: executing ? '#ccc' : '#1976d2', color: '#fff',
          cursor: executing ? 'not-allowed' : 'pointer', fontSize: 13,
        }}
      >
        {executing ? '执行中...' : (hasArgs ? '执行' : '运行')}
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

function ToolCard({ tool }: { tool: ToolInfo }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{
      marginBottom: 4, borderRadius: 8, border: '1px solid #eee',
      overflow: 'hidden', background: '#fff',
    }}>
      <div
        onClick={() => setOpen(!open)}
        style={{
          padding: '8px 12px', cursor: 'pointer', display: 'flex',
          alignItems: 'center', gap: 8, fontSize: 13,
          transition: 'background 0.1s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = '#fafafa')}
        onMouseLeave={(e) => (e.currentTarget.style.background = '#fff')}
      >
        <code style={{ fontWeight: 600, color: '#333', fontSize: 13 }}>{tool.name}</code>
        <span style={{ color: '#999', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>
          {tool.description}
        </span>
        <span style={{ color: '#bbb', fontSize: 11, flexShrink: 0 }}>
          {open ? '收起' : '展开'}
        </span>
      </div>
      {open && (
        <div style={{ padding: '0 12px 12px' }}>
          <ToolExecutor tool={tool} />
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

  const categoryOrder = ['计算', '天气', '审核', '浏览器', '小猿任务', '其他']
  const sortedCats = Object.keys(grouped).sort(
    (a, b) => categoryOrder.indexOf(a) - categoryOrder.indexOf(b)
  )

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: 20, height: '100%', overflowY: 'auto' }}>
      <h2 style={{ marginBottom: 16, fontSize: 18, fontWeight: 600 }}>
        工具面板
        <span style={{ fontSize: 14, color: '#999', fontWeight: 400, marginLeft: 8 }}>
          {tools.length} 个工具 · {Object.keys(grouped).length} 类
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
              <ToolCard key={tool.name} tool={tool} />
            ))}
          </div>
        )
      })}
    </div>
  )
}
