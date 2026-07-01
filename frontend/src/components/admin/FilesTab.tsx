import { useState, useEffect } from 'react'
import { Spinner, Empty, ErrorMsg, Card, safeJson, headers, API_BASE } from './shared'

export default function FilesTab() {
  const [dirs, setDirs] = useState<{ name: string; path: string; is_dir: boolean; size_kb: number }[]>([])
  const [currentPath, setCurrentPath] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [preview, setPreview] = useState<any>(null)

  const load = async (p: string) => {
    setLoading(true); setError(''); setCurrentPath(p)
    try {
      const res = await fetch(`${API_BASE}/admin/files?path=` + encodeURIComponent(p), { headers: headers() })
      const d = await safeJson(res)
      if (d && d.items) setDirs(d.items); else if (d && d.error) setError(d.error)
    } catch { setError('加载文件列表失败') }
    setLoading(false)
  }
  useEffect(() => { load('') }, [])

  const goUp = () => { const parts = currentPath.split(/[/\\]/).filter(Boolean); parts.pop(); load(parts.join('/')) }

  const handlePreview = async (d: { name: string; path: string; is_dir: boolean }) => {
    if (d.is_dir) { load(d.path); return }
    setError('')
    try {
      const res = await fetch(`${API_BASE}/admin/file/read?path=` + encodeURIComponent(d.path), { headers: headers() })
      const r = await safeJson(res)
      if (r && r.error) { setError(r.error); return }
      setPreview({ ...r, name: d.name })
    } catch { setError('读取文件失败') }
  }

  return (
    <div>
      {error && <ErrorMsg msg={error} />}
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-secondary)' }}>
        {currentPath && <button onClick={goUp} style={{ fontSize: 12, padding: '4px 10px', border: '1px solid var(--border)', background: 'var(--bg-primary)', borderRadius: 4, cursor: 'pointer', color: 'var(--text-primary)' }}>上级目录</button>}
        <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text-primary)' }}>data/{currentPath || '.'}</span>
        <button onClick={() => load(currentPath)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--accent)' }}>刷新</button>
      </div>
      {loading ? <Spinner /> : (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: 'var(--bg-tertiary)' }}>
              {['名称', '类型', '大小'].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600 }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {dirs.length === 0 && <tr><td colSpan={3}><Empty msg="空目录" /></td></tr>}
              {dirs.map((d, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border-light)', cursor: 'pointer', transition: 'background 0.1s', color: 'var(--text-primary)' }}
                  onClick={() => handlePreview(d)}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--hover-bg)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = '')}>
                  <td style={{ padding: '10px 14px', color: d.is_dir ? 'var(--accent)' : 'var(--text-primary)', fontWeight: d.is_dir ? 600 : 400 }}>{d.is_dir ? '📁 ' : '📄 '}{d.name}</td>
                  <td style={{ padding: '10px 14px', color: 'var(--text-secondary)', fontSize: 12 }}>{d.is_dir ? '目录' : '文件'}</td>
                  <td style={{ padding: '10px 14px', color: 'var(--text-secondary)', fontSize: 12 }}>{d.is_dir ? '-' : `${d.size_kb} KB`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {preview && (
        <div onClick={() => setPreview(null)} style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: '80%', maxHeight: '85%', background: 'var(--bg-primary)', borderRadius: 12, padding: 24, overflow: 'auto', minWidth: 360, boxShadow: '0 8px 40px var(--shadow-md)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{preview.name}</span>
              <span onClick={() => setPreview(null)} style={{ cursor: 'pointer', fontSize: 18, color: 'var(--text-secondary)', lineHeight: 1 }}>✕</span>
            </div>
            {preview.type === 'image' && <img src={`data:image/${preview.ext?.replace('.', '')};base64,${preview.data}`} style={{ maxWidth: '100%', borderRadius: 8 }} />}
            {preview.type === 'text' && <pre style={{ background: 'var(--bg-tertiary)', borderRadius: 8, padding: 16, fontSize: 13, lineHeight: 1.6, overflow: 'auto', maxHeight: '65vh', whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: 'var(--text-primary)' }}>{preview.content}</pre>}
            {!preview.type && <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>{preview.detail || '无法预览'}</div>}
          </div>
        </div>
      )}
    </div>
  )
}
