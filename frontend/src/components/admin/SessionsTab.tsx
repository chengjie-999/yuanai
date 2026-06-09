import { useState, useEffect } from 'react'
import { Spinner, Empty, ErrorMsg, Card, btnDangerSm, inputStyle, headers, API_BASE } from './shared'

export default function SessionsTab() {
  const [sessions, setSessions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')

  const load = () => {
    setError('')
    fetch(`${API_BASE}/chat/sessions`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then((d) => { if (Array.isArray(d)) setSessions(d) })
      .catch((e) => setError(`加载会话列表失败: ${e.message}`))
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  const handleDelete = async (id: string) => {
    if (!confirm('确认删除此会话？')) return
    const res = await fetch(`${API_BASE}/chat/session/${id}`, { method: 'DELETE', headers: headers() })
    if (res.ok) load()
  }

  const filtered = search.trim()
    ? sessions.filter((s) => s.title?.toLowerCase().includes(search.toLowerCase()) || s.session_id?.includes(search) || s.username?.toLowerCase().includes(search.toLowerCase()))
    : sessions

  return (
    <>
      {error && <ErrorMsg msg={error} onRetry={load} />}
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, alignItems: 'center' }}>
        <div style={{ flex: 1 }} />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜索标题、用户或 ID..." style={{ ...inputStyle, width: 240 }} />
      </div>
      {loading ? <Spinner /> : (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: '#f5f5f8' }}>
              {['会话 ID', '标题', '用户', '消息数', '创建时间', '更新时间', '操作'].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600, borderBottom: '2px solid #e0e0e0' }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {filtered.length === 0 && <tr><td colSpan={7}><Empty msg={search ? '无匹配会话' : '暂无会话'} /></td></tr>}
              {filtered.map((s) => (
                <tr key={s.session_id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '10px 14px', fontFamily: 'monospace', fontSize: 11, color: '#888', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={s.session_id}>{s.session_id.slice(0, 12)}...</td>
                  <td style={{ padding: '10px 14px', fontWeight: 600, color: '#333', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.title || '未命名'}</td>
                  <td style={{ padding: '10px 14px', color: '#666', fontSize: 12 }}>{s.username}</td>
                  <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{s.message_count ?? '-'}</td>
                  <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{s.create_time?.slice(0, 16)}</td>
                  <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{s.update_time?.slice(0, 16)}</td>
                  <td style={{ padding: '10px 14px' }}><button onClick={() => handleDelete(s.session_id)} style={btnDangerSm}>删除</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
