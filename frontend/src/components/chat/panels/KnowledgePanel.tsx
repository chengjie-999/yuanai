import { useState, useRef, useEffect } from 'react'
import { API_BASE } from '../../../api'

export default function KnowledgePanel() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<any[]>([])
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState('')
  const [hasSearched, setHasSearched] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSearch = async () => {
    if (!query.trim()) return
    setSearching(true); setError('')
    try {
      const token = localStorage.getItem('token') || ''
      const res = await fetch(`${API_BASE}/knowledge/search?q=${encodeURIComponent(query.trim())}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error()
      const data = await res.json()
      setResults(data.results || [])
      setHasSearched(true)
    } catch { setError('检索失败') }
    setSearching(false)
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border-light)', display: 'flex', gap: 6, flexShrink: 0 }}>
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="搜索知识库..."
          style={{
            flex: 1, padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)',
            fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)',
          }}
        />
        <button
          onClick={handleSearch}
          disabled={searching || !query.trim()}
          style={{
            padding: '6px 12px', borderRadius: 6, border: 'none',
            background: 'var(--accent)', color: '#fff', cursor: 'pointer', fontSize: 12,
            opacity: searching || !query.trim() ? 0.5 : 1, whiteSpace: 'nowrap',
          }}
        >{searching ? '...' : '搜索'}</button>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '8px 14px' }}>
        {error && (
          <div style={{ padding: 8, color: '#e53935', fontSize: 12 }}>{error}</div>
        )}
        {!hasSearched ? (
          <div style={{ textAlign: 'center', color: '#ccc', padding: 40, fontSize: 13 }}>
            输入关键词搜索知识库
          </div>
        ) : results.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#ccc', padding: 40, fontSize: 13 }}>
            无匹配结果
          </div>
        ) : (
          results.map((r: any, i: number) => (
            <div key={i} style={{
              padding: '10px 0', borderBottom: i < results.length - 1 ? '1px solid #f5f5f5' : 'none',
            }}>
              <div style={{ fontSize: 11, color: '#1976d2', marginBottom: 4, display: 'flex', gap: 8 }}>
                <span>{r.source}</span>
                {r.score != null && <span style={{ color: '#bbb' }}>{(r.score * 100).toFixed(0)}%</span>}
              </div>
              <div style={{ fontSize: 13, color: '#333', lineHeight: 1.6 }}>{r.content}</div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
