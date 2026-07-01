import { useState, useEffect } from 'react'
import { Empty, ErrorMsg, Card, btnPrimary, btnDangerSm, inputStyle } from './shared'
import { fetchWebsites, addWebsite, deleteWebsite } from '../../api'

export default function WebsitesTab() {
  const [websites, setWebsites] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [newName, setNewName] = useState(''); const [newUrl, setNewUrl] = useState(''); const [newRemark, setNewRemark] = useState('')
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})

  const parseUrls = (w: any): string[] => {
    if (Array.isArray(w.url)) return w.url
    if (typeof w.url === 'string') { try { const j = JSON.parse(w.url); return Array.isArray(j) ? j : [w.url] } catch { return [w.url] } }
    return [String(w.url)]
  }
  const load = async () => { setLoading(true); setError(''); setWebsites(await fetchWebsites()); setLoading(false) }
  useEffect(() => { load() }, [])

  const handleAdd = async () => {
    if (!newName.trim() || !newUrl.trim()) return
    const urls = newUrl.split(/[,，]/).map((u) => u.trim()).filter(Boolean)
    const r = await addWebsite(newName, JSON.stringify(urls), newRemark)
    if (r.error) { setError(r.error); return }
    setShowAdd(false); setNewName(''); setNewUrl(''); setNewRemark(''); setError(''); load()
  }
  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`确定删除网站 "${name}"？`)) return
    if (await deleteWebsite(id)) load()
  }

  return (
    <>
      {error && <ErrorMsg msg={error} />}
      <div style={{ marginBottom: 12 }}>
        {!showAdd ? <button onClick={() => setShowAdd(true)} style={btnPrimary}>+ 添加网站</button> : (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="名称" style={{ ...inputStyle, width: 130 }} />
            <input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="URL（多个用逗号分隔）" style={{ ...inputStyle, width: 320 }} />
            <input value={newRemark} onChange={(e) => setNewRemark(e.target.value)} placeholder="备注（可选）" style={{ ...inputStyle, width: 150 }} />
            <button onClick={handleAdd} style={btnPrimary}>确定</button>
            <button onClick={() => setShowAdd(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--text-muted)' }}>取消</button>
          </div>
        )}
      </div>
      {loading ? <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 40, fontSize: 13 }}>加载中...</div> : (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: 'var(--bg-tertiary)' }}>
              {['名称', 'URL', '备注', '操作'].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, borderBottom: '2px solid var(--border)' }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {websites.length === 0 && <tr><td colSpan={4}><Empty msg="暂无网站" /></td></tr>}
              {websites.map((w) => {
                const urls = parseUrls(w); const isExpanded = expanded[w.id]
                return (
                  <tr key={w.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--text-primary)' }}>{w.name}</td>
                    <td style={{ padding: '10px 14px', color: 'var(--accent)', fontSize: 12 }}>
                      <div style={{ wordBreak: 'break-all' }}>{urls[0]}</div>
                      {urls.length > 1 && (isExpanded ? urls.slice(1).map((u, i) => <div key={i} style={{ marginTop: 2, opacity: 0.8, wordBreak: 'break-all' }}>{u}</div>) : <span onClick={() => setExpanded((p) => ({ ...p, [w.id]: true }))} style={{ cursor: 'pointer', fontSize: 11, color: 'var(--text-muted)' }}>+{urls.length - 1} 个更多</span>)}
                    </td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontSize: 12 }}>{w.remark || '-'}</td>
                    <td style={{ padding: '10px 14px' }}><button onClick={() => handleDelete(w.id, w.name)} style={btnDangerSm}>删除</button></td>
                  </tr>)
              })}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
