import { useState, useEffect, useMemo } from 'react'
import { Spinner, Empty, ErrorMsg, Card, CardHeader, badge, headers, API_BASE } from './shared'

export default function ToolsTab() {
  const [tools, setTools] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const load = () => {
    setError('')
    fetch(`${API_BASE}/tools/`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((d) => { if (Array.isArray(d)) setTools(d) })
      .catch(() => setError('加载工具列表失败'))
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  const grouped = useMemo(() => {
    const map: Record<string, any[]> = {}
    tools.forEach((t: any) => {
      const cat = t.category || 'other'
      if (!map[cat]) map[cat] = []
      map[cat].push(t)
    })
    return Object.entries(map).sort(([a], [b]) => a.localeCompare(b))
  }, [tools])

  return (
    <>
      {error && <ErrorMsg msg={error} onRetry={load} />}
      {loading ? <Spinner /> : tools.length === 0 ? <Empty msg="暂无工具" /> : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ fontSize: 13, color: '#666' }}>共 {tools.length} 个工具，{grouped.length} 个分类</span>
            <div style={{ flex: 1 }} />
            <button onClick={load} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: '#1976d2' }}>刷新</button>
          </div>
          {grouped.map(([cat, items]) => (
            <Card key={cat}>
              <CardHeader
                title={`${cat} (${items.length})`}
                action={
                  <button
                    onClick={() => setExpanded((p) => ({ ...p, [cat]: !p[cat] }))}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: '#999' }}
                  >{expanded[cat] ? '收起' : '展开'}</button>
                }
              />
              {(expanded[cat] !== false) && (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: '#f5f5f8' }}>
                      {['工具名', '描述', ''].map((h) => <th key={h} style={{ padding: '8px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600 }}>{h}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((t: any) => (
                      <tr key={t.name} style={{ borderBottom: '1px solid #f0f0f0' }}>
                        <td style={{ padding: '8px 14px', fontFamily: 'monospace', fontSize: 12, color: '#333' }}>
                          {t.name}
                          {t.admin_only && badge('管理员', '#e65100')}
                        </td>
                        <td style={{ padding: '8px 14px', fontSize: 12, color: '#666', lineHeight: 1.5 }}>{t.description}</td>
                        <td style={{ padding: '8px 14px' }}>
                          {t.args && Object.keys(t.args).length > 0 && (
                            <span style={{ fontSize: 11, color: '#bbb' }}>{Object.keys(t.args).length} 参数</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          ))}
        </div>
      )}
    </>
  )
}
