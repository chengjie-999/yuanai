import { useState, useEffect } from 'react'
import { fetchTools } from '../api'
import type { ToolInfo } from '../types'

const API_BASE = '/api/v1'

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

  return (
    <div style={{ marginTop: 12, borderTop: '1px solid #eee', paddingTop: 12 }}>
      {Object.keys(properties).length > 0 && (
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
                  width: '100%',
                  padding: '6px 8px',
                  borderRadius: 4,
                  border: '1px solid #ccc',
                  fontSize: 13,
                  boxSizing: 'border-box',
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
          padding: '6px 16px',
          borderRadius: 4,
          border: 'none',
          background: executing ? '#ccc' : '#1976d2',
          color: '#fff',
          cursor: executing ? 'not-allowed' : 'pointer',
          fontSize: 13,
        }}
      >
        {executing ? '执行中...' : '执行'}
      </button>
      {result !== null && (
        <div style={{
          marginTop: 8,
          padding: 8,
          background: '#f0faf0',
          borderRadius: 4,
          fontSize: 13,
          color: '#333',
          whiteSpace: 'pre-wrap',
          maxHeight: 200,
          overflow: 'auto',
        }}>
          {result}
        </div>
      )}
      {error && (
        <div style={{
          marginTop: 8,
          padding: 8,
          background: '#fff0f0',
          borderRadius: 4,
          fontSize: 13,
          color: '#c00',
        }}>
          ❌ {error}
        </div>
      )}
    </div>
  )
}

export default function ToolsPage() {
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchTools()
      .then((data) => setTools(data))
      .catch((e) => console.error(e))
      .finally(() => setLoading(false))
  }, [])

  const filtered = tools.filter((t) =>
    t.name.toLowerCase().includes(search.toLowerCase()) ||
    t.description.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: 20, height: '100%', overflowY: 'auto' }}>
      <h2 style={{ marginBottom: 16 }}>工具面板 ({tools.length})</h2>
      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="搜索工具..."
        style={{
          width: '100%',
          padding: 10,
          borderRadius: 6,
          border: '1px solid #ccc',
          marginBottom: 16,
          boxSizing: 'border-box',
        }}
      />
      {loading && <div style={{ color: '#999' }}>加载中...</div>}
      {filtered.map((tool) => (
        <div key={tool.name} style={{
          marginBottom: 8,
          border: '1px solid #e0e0e0',
          borderRadius: 8,
          overflow: 'hidden',
        }}>
          <div
            onClick={() => setExpanded(expanded === tool.name ? null : tool.name)}
            style={{
              padding: '10px 14px',
              cursor: 'pointer',
              background: expanded === tool.name ? '#f5f5f5' : '#fff',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <strong style={{ fontSize: 14 }}>{tool.name}</strong>
              <div style={{ fontSize: 12, color: '#666', marginTop: 2 }}>{tool.description}</div>
            </div>
            <span style={{ color: '#999', fontSize: 12 }}>{expanded === tool.name ? '收起' : '展开'}</span>
          </div>
          {expanded === tool.name && (
            <div style={{ padding: '0 14px 14px' }}>
              <ToolExecutor tool={tool} />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
