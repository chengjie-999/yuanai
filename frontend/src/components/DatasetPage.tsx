import { useState, useEffect, useCallback, useRef } from 'react'
import { uploadDataset, fetchDatasets, fetchDatasetPreview, deleteDataset } from '../api'

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export default function DatasetPage() {
  const [datasets, setDatasets] = useState<any[]>([])
  const [uploading, setUploading] = useState(false)
  const [preview, setPreview] = useState<any>(null)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    const data = await fetchDatasets()
    setDatasets(data)
  }, [])

  useEffect(() => { load() }, [load])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError('')
    try {
      await uploadDataset(file)
      load()
    } catch (err: any) {
      setError(err.message || 'upload failed')
    }
    setUploading(false)
    if (fileRef.current) fileRef.current.value = ''
  }

  const handlePreview = async (id: number) => {
    const data = await fetchDatasetPreview(id)
    setPreview(data)
  }

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Delete "${name}"?`)) return
    await deleteDataset(id)
    if (preview?.id === id) setPreview(null)
    load()
  }

  return (
    <div style={{ height: '100%', display: 'flex', padding: '20px 24px', gap: 16, overflow: 'auto', background: '#f8f9fb' }}>
      {/* left: list */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0, color: '#2c2c54' }}>📊 数据工作台</h2>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls,.json" hidden
            onChange={handleUpload} />
          <button onClick={() => fileRef.current?.click()} disabled={uploading}
            className="btn btn-primary"
            style={{ padding: '8px 20px', fontSize: 14, fontWeight: 600, opacity: uploading ? 0.6 : 1 }}>
            {uploading ? '上传中...' : '📤 上传文件'}
          </button>
          <span style={{ fontSize: 12, color: '#999' }}>支持 CSV / Excel / JSON</span>
        </div>
        {error && <div style={{ color: '#e53935', fontSize: 13 }}>{error}</div>}

        <div style={{ flex: 1, background: '#fff', borderRadius: 10, border: '1px solid #eee', overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f5f5f8', textAlign: 'left' }}>
                <th style={{ padding: '10px 14px', fontWeight: 600, color: '#333' }}>名称</th>
                <th style={{ padding: '10px 14px', fontWeight: 600, color: '#333' }}>类型</th>
                <th style={{ padding: '10px 14px', fontWeight: 600, color: '#333' }}>大小</th>
                <th style={{ padding: '10px 14px', fontWeight: 600, color: '#333' }}>行数</th>
                <th style={{ padding: '10px 14px', fontWeight: 600, color: '#333' }}>时间</th>
                <th style={{ padding: '10px 14px', fontWeight: 600, color: '#333' }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {datasets.length === 0 && (
                <tr><td colSpan={6} style={{ padding: 40, textAlign: 'center', color: '#999' }}>暂无数据集，请上传文件</td></tr>
              )}
              {datasets.map((ds) => (
                <tr key={ds.id} style={{ borderBottom: '1px solid #f0f0f0', cursor: 'pointer' }}
                  onClick={() => handlePreview(ds.id)}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#fafbfc')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = '')}>
                  <td style={{ padding: '10px 14px', color: '#1976d2' }}>{ds.name}</td>
                  <td style={{ padding: '10px 14px', color: '#666' }}>{ds.file_type}</td>
                  <td style={{ padding: '10px 14px', color: '#666' }}>{formatSize(ds.file_size)}</td>
                  <td style={{ padding: '10px 14px', color: '#666' }}>{ds.row_count || '-'}</td>
                  <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{ds.create_time}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <button onClick={(e) => { e.stopPropagation(); handleDelete(ds.id, ds.name) }}
                      style={{ background: 'none', border: 'none', color: '#e53935', cursor: 'pointer', fontSize: 13, padding: 0 }}>删除</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* full-screen preview modal */}
      {preview && (
        <div onClick={() => setPreview(null)} style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: '90vw', maxHeight: '90vh', width: 900, background: '#fff', borderRadius: 12, overflow: 'auto', cursor: 'default', boxShadow: '0 8px 40px rgba(0,0,0,0.3)' }}>
            <div style={{ padding: '14px 18px', background: '#f5f5f8', fontSize: 14, fontWeight: 600, color: '#333', borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'space-between', position: 'sticky', top: 0, zIndex: 1 }}>
              <span>{preview.name}</span>
              <span onClick={() => setPreview(null)} style={{ cursor: 'pointer', color: '#999', fontSize: 18, lineHeight: 1 }}>✕</span>
            </div>
            <div style={{ padding: 16, fontSize: 12 }}>
              <div style={{ marginBottom: 10, color: '#666', display: 'flex', gap: 16 }}>
                <span>列数: {preview.columns?.length || 0}</span>
                <span>行数: {preview.row_count}</span>
                <span>大小: {formatSize(preview.file_size)}</span>
              </div>
              {preview.columns && (
                <div style={{ marginBottom: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {preview.columns.map((c: any, i: number) => (
                    <span key={i} style={{ background: '#e3f2fd', color: '#1565c0', padding: '3px 10px', borderRadius: 4, fontSize: 12 }}>
                      {c.name} <span style={{ opacity: 0.5 }}>{c.dtype}</span>
                    </span>
                  ))}
                </div>
              )}
              <div style={{ overflow: 'auto', maxHeight: '60vh' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr>
                      {preview.columns?.map((c: any, i: number) => (
                        <th key={i} style={{ padding: '8px 10px', borderBottom: '2px solid #e0e0e0', color: '#333', textAlign: 'left', whiteSpace: 'nowrap', position: 'sticky', top: 0, background: '#fff' }}>{c.name}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.preview_rows?.map((row: any, ri: number) => (
                      <tr key={ri} style={{ background: ri % 2 === 0 ? '#fafbfc' : '#fff' }}>
                        {preview.columns?.map((c: any, ci: number) => (
                          <td key={ci} style={{ padding: '5px 10px', borderBottom: '1px solid #f0f0f0', color: '#555', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {String(row[c.name] ?? '')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
