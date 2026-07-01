import { useState, useEffect, useRef } from 'react'
import { Spinner, Empty, ErrorMsg, Card, CardHeader, btnPrimary, inputStyle, badge, headers, safeJson, API_BASE } from './shared'

export default function KnowledgeTab() {
  const [sources, setSources] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [searchQ, setSearchQ] = useState('')
  const [searchResult, setSearchResult] = useState<any>(null)
  const [searching, setSearching] = useState(false)
  const [rebuilding, setRebuilding] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = () => {
    setError('')
    fetch(`${API_BASE}/knowledge/sources`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((d) => { if (Array.isArray(d)) setSources(d) })
      .catch(() => setError('加载知识库失败'))
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return
    setError('')
    const form = new FormData(); form.append('file', file); form.append('visibility', 'shared')
    const res = await fetch(`${API_BASE}/knowledge/upload`, { method: 'POST', headers: { Authorization: headers()['Authorization'] }, body: form })
    if (!res.ok) { const d = await safeJson(res); setError(d?.detail || '上传失败'); return }
    load()
  }

  const handleDelete = async (source: string) => {
    if (!confirm(`确定删除知识源 "${source}"？`)) return
    const res = await fetch(`${API_BASE}/knowledge/${source}`, { method: 'DELETE', headers: headers() })
    if (res.ok) load()
  }

  const handleRebuild = async () => {
    if (!confirm('确定全量重建知识库？此操作可能需要几分钟。')) return
    setRebuilding(true); setError('')
    try {
      const res = await fetch(`${API_BASE}/knowledge/rebuild`, { method: 'POST', headers: headers() })
      if (!res.ok) throw new Error()
      load()
    }
    catch { setError('重建失败') }
    setRebuilding(false)
  }

  const handleSearch = async () => {
    if (!searchQ.trim()) return
    setSearching(true); setError('')
    try {
      const res = await fetch(`${API_BASE}/knowledge/search?q=${encodeURIComponent(searchQ.trim())}`, { headers: headers() })
      if (!res.ok) throw new Error()
      setSearchResult(await res.json())
    }
    catch { setError('检索失败') }
    setSearching(false)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {error && <ErrorMsg msg={error} onRetry={load} />}

      <Card>
        <CardHeader title="知识库检索" />
        <div style={{ padding: '12px 20px', display: 'flex', gap: 8 }}>
          <input value={searchQ} onChange={(e) => setSearchQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSearch()} placeholder="输入关键词检索知识库..." style={{ ...inputStyle, flex: 1 }} />
          <button onClick={handleSearch} disabled={searching} style={btnPrimary}>{searching ? '检索中...' : '搜索'}</button>
        </div>
        {searchResult && (
          <div style={{ maxHeight: 400, overflow: 'auto', padding: '0 20px 16px' }}>
            {searchResult.results?.length > 0 ? searchResult.results.map((r: any, i: number) => (
              <div key={i} style={{ padding: '10px 0', borderBottom: '1px solid var(--border-light)' }}>
                <div style={{ fontSize: 12, color: 'var(--accent)', marginBottom: 4 }}>来源: {r.source} | 相似度: {(r.score * 100).toFixed(0)}%</div>
                <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6 }}>{r.content}</div>
              </div>
            )) : <Empty msg="无匹配结果" />}
          </div>
        )}
      </Card>

      {loading ? <Spinner /> : (
        <Card>
          <CardHeader title={`知识源 (${sources.length})`} action={
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => fileRef.current?.click()} style={{ ...btnPrimary, fontSize: 12, padding: '5px 12px' }}>+ 上传 ZIP</button>
              <button onClick={handleRebuild} disabled={rebuilding} style={{ fontSize: 12, padding: '5px 12px', color: 'var(--danger)', border: '1px solid var(--danger)', background: 'none', borderRadius: 6, cursor: 'pointer' }}>{rebuilding ? '重建中...' : '重建索引'}</button>
              <input ref={fileRef} type="file" accept=".zip" onChange={handleUpload} style={{ display: 'none' }} />
            </div>
          } />
          {sources.length === 0 ? <Empty msg="暂无知识源" /> : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead><tr style={{ background: 'var(--bg-tertiary)' }}>
                {['名称', '分块数', '图片数', '可见性', '操作'].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, borderBottom: '2px solid var(--border)' }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {sources.map((s) => (
                  <tr key={s.source} style={{ borderBottom: '1px solid var(--border-light)' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--text-primary)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={s.source}>{s.source}</td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontSize: 12 }}>{s.chunks}</td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontSize: 12 }}>{s.images}</td>
                    <td style={{ padding: '10px 14px' }}>{s.visibility === 'shared' ? badge('共享', '#4caf50') : badge('私有', '#ff9800')}</td>
                    <td style={{ padding: '10px 14px' }}><button onClick={() => handleDelete(s.source)} style={{ fontSize: 12, padding: '4px 10px', color: 'var(--danger)', border: '1px solid var(--danger)', background: 'none', borderRadius: 4, cursor: 'pointer' }}>删除</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}
    </div>
  )
}
