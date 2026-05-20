import { useState, useEffect, useCallback, useRef } from 'react'
import { API_BASE, getToken } from '../api'

function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

interface KnowledgeSource {
  source: string
  chunks: number
  images: number
  visibility: 'shared' | 'private'
}

export default function KnowledgePage() {
  const [sources, setSources] = useState<KnowledgeSource[]>([])
  const [uploading, setUploading] = useState(false)
  const [visibility, setVisibility] = useState<'shared' | 'private'>('shared')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const loadSources = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/knowledge/sources`, { headers: authHeaders() })
      if (!res.ok) return
      const data = await res.json()
      setSources(data)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadSources() }, [loadSources])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.zip')) {
      setError('仅支持 .zip 压缩包')
      return
    }
    setUploading(true)
    setError('')
    setMessage('')
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(
        `${API_BASE}/knowledge/upload?visibility=${visibility}`,
        { method: 'POST', headers: authHeaders(), body: form },
      )
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '上传失败')
      setMessage(data.message || '导入成功')
      loadSources()
    } catch (err: any) {
      setError(err.message || '上传失败')
    }
    setUploading(false)
    if (fileRef.current) fileRef.current.value = ''
  }

  const handleDelete = async (source: string) => {
    if (!confirm(`确定删除 "${source}"？`)) return
    try {
      const res = await fetch(
        `${API_BASE}/knowledge/${encodeURIComponent(source)}`,
        { method: 'DELETE', headers: authHeaders() },
      )
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || '删除失败')
      }
      loadSources()
    } catch (err: any) {
      setError(err.message || '删除失败')
    }
  }

  const handleRebuild = async () => {
    if (!confirm('确定全量重建知识库？将重新生成所有向量。')) return
    setMessage('')
    setError('')
    try {
      const res = await fetch(`${API_BASE}/knowledge/rebuild`, {
        method: 'POST', headers: authHeaders(),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '重建失败')
      setMessage('知识库重建完成')
      loadSources()
    } catch (err: any) {
      setError(err.message || '重建失败')
    }
  }

  const totalChunks = sources.reduce((s, c) => s + c.chunks, 0)
  const totalImages = sources.reduce((s, c) => s + c.images, 0)

  return (
    <div style={{ height: '100%', display: 'flex', padding: '20px 24px', gap: 16, overflow: 'auto', background: '#f8f9fb' }}>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0, color: '#2c2c54' }}>📚 知识库</h2>
          <span style={{ fontSize: 12, color: '#999' }}>
            {sources.length} 个来源 · {totalChunks} 节点 · {totalImages} 张图
          </span>
        </div>

        {/* Upload area */}
        <div style={{
          background: '#fff', borderRadius: 10, border: '1px solid #eee', padding: 20,
        }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <input ref={fileRef} type="file" accept=".zip" hidden onChange={handleUpload} />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="btn btn-primary"
              style={{ padding: '10px 24px', fontSize: 14, fontWeight: 600, opacity: uploading ? 0.6 : 1 }}>
              {uploading ? '解析中...' : '📤 上传 ZIP'}
            </button>

            <select
              value={visibility}
              onChange={(e) => setVisibility(e.target.value as any)}
              style={{
                padding: '10px 14px', fontSize: 13, border: '1px solid #ddd',
                borderRadius: 6, background: '#fff', cursor: 'pointer',
              }}
            >
              <option value="shared">🌐 共享知识库</option>
              <option value="private">🔒 私有知识库</option>
            </select>

            <button
              onClick={handleRebuild}
              style={{
                padding: '10px 18px', fontSize: 13, border: '1px solid #ddd',
                borderRadius: 6, background: '#fff', cursor: 'pointer', color: '#666',
              }}
            >
              🔄 全量重建
            </button>
          </div>

          <div style={{ marginTop: 12, fontSize: 12, color: '#999' }}>
            MindMaster 批量导出 Markdown → 文件夹打包为 ZIP → 上传
          </div>

          {message && <div style={{ marginTop: 10, padding: '8px 14px', background: '#e8f5e9', borderRadius: 6, color: '#2e7d32', fontSize: 13 }}>{message}</div>}
          {error && <div style={{ marginTop: 10, padding: '8px 14px', background: '#fce4ec', borderRadius: 6, color: '#c62828', fontSize: 13 }}>{error}</div>}
        </div>

        {/* Source list */}
        <div style={{ flex: 1, background: '#fff', borderRadius: 10, border: '1px solid #eee', overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f5f5f8', textAlign: 'left', position: 'sticky', top: 0 }}>
                <th style={{ padding: '10px 14px', fontWeight: 600, color: '#333' }}>来源</th>
                <th style={{ padding: '10px 14px', fontWeight: 600, color: '#333', width: 100 }}>节点数</th>
                <th style={{ padding: '10px 14px', fontWeight: 600, color: '#333', width: 80 }}>图片</th>
                <th style={{ padding: '10px 14px', fontWeight: 600, color: '#333', width: 100 }}>可见范围</th>
                <th style={{ padding: '10px 14px', fontWeight: 600, color: '#333', width: 80 }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {sources.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ padding: 40, textAlign: 'center', color: '#999', fontSize: 14 }}>
                    暂无知识库，上传 ZIP 开始构建
                  </td>
                </tr>
              )}
              {sources.map((s) => (
                <tr key={s.source} style={{ borderTop: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 500, color: '#333' }}>
                    {s.source}
                  </td>
                  <td style={{ padding: '10px 14px', color: '#666' }}>{s.chunks}</td>
                  <td style={{ padding: '10px 14px', color: '#666' }}>{s.images || '-'}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: 4, fontSize: 12,
                      background: s.visibility === 'shared' ? '#e3f2fd' : '#fce4ec',
                      color: s.visibility === 'shared' ? '#1565c0' : '#c62828',
                    }}>
                      {s.visibility === 'shared' ? '共享' : '私有'}
                    </span>
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    <button
                      onClick={() => handleDelete(s.source)}
                      style={{
                        background: 'none', border: 'none', color: '#e53935', cursor: 'pointer',
                        fontSize: 13, padding: '4px 8px',
                      }}
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
