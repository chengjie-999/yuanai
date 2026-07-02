import { useState, useEffect, useRef } from 'react'
import { Spinner, Empty, ErrorMsg, Card, CardHeader, btnDangerSm, headers, API_BASE } from './shared'
import { uploadDataset } from '../../api'
import AnalysisResultView from '../AnalysisResultView'

export default function DatasetsTab() {
  const [datasets, setDatasets] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [preview, setPreview] = useState<any>(null)
  const [analysis, setAnalysis] = useState<any>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = () => {
    setError('')
    fetch(`${API_BASE}/data/datasets`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((d) => { if (Array.isArray(d)) setDatasets(d) })
      .catch(() => setError('加载数据集失败'))
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true); setError('')
    const r = await uploadDataset(file)
    if (r?.id) load()
    else setError(r?.detail || '上传失败')
    setUploading(false)
    if (fileRef.current) fileRef.current.value = ''
  }

  const handleDelete = async (id: number) => {
    if (!confirm('确认删除此数据集？')) return
    const res = await fetch(`${API_BASE}/data/dataset/${id}`, { method: 'DELETE', headers: headers() })
    if (res.ok) load()
  }

  const handleAnalyze = async (id: number) => {
    setAnalyzing(true); setError('')
    try {
      const res = await fetch(`${API_BASE}/data/analyze/${id}?charts=true&force=true`, { headers: headers() })
      if (!res.ok) throw new Error()
      setAnalysis(await res.json())
    } catch { setError('分析失败') }
    setAnalyzing(false)
  }

  return (
    <>
      {error && <ErrorMsg msg={error} onRetry={load} />}
      <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls,.json" onChange={handleUpload} style={{ display: 'none' }} />
      {loading ? <Spinner /> : datasets.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Empty msg="暂无数据集" />
          <button onClick={() => fileRef.current?.click()} disabled={uploading}
            style={{ fontSize: 12, padding: '5px 14px', color: 'var(--accent)', border: '1px solid var(--accent)', background: 'none', borderRadius: 4, cursor: 'pointer', marginTop: 8 }}>
            {uploading ? '上传中...' : '+ 上传 CSV/Excel/JSON'}
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Card>
            <CardHeader title={`数据集 (${datasets.length})`} action={
              <>
                <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls,.json" onChange={handleUpload} style={{ display: 'none' }} />
                <button onClick={() => fileRef.current?.click()} disabled={uploading}
                  style={{ fontSize: 12, padding: '4px 10px', color: 'var(--accent)', border: '1px solid var(--accent)', background: 'none', borderRadius: 4, cursor: 'pointer' }}>
                  {uploading ? '上传中...' : '+ 上传'}
                </button>
              </>
            } />
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead><tr style={{ background: 'var(--bg-tertiary)' }}>
                {['名称', '类型', '大小', '行数', '上传时间', '操作'].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, borderBottom: '2px solid var(--border)' }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {datasets.map((d: any) => (
                  <tr key={d.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--text-primary)', cursor: 'pointer' }} onClick={() => setPreview(d)}>{d.name}</td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontSize: 12 }}>{d.file_type}</td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontSize: 12 }}>{d.file_size ? `${(d.file_size / 1024).toFixed(1)} KB` : '-'}</td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontSize: 12 }}>{d.row_count ?? '-'}</td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontSize: 12 }}>{d.create_time?.slice(0, 16)}</td>
                    <td style={{ padding: '10px 14px', display: 'flex', gap: 6 }}>
                      <button onClick={() => handleAnalyze(d.id)} disabled={analyzing} style={{ fontSize: 12, padding: '4px 10px', color: 'var(--accent)', border: '1px solid var(--accent)', background: 'none', borderRadius: 4, cursor: 'pointer' }}>{analyzing ? '分析中...' : '分析'}</button>
                      <button onClick={() => handleDelete(d.id)} style={btnDangerSm}>删除</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          {preview && preview.preview_rows && (
            <Card>
              <CardHeader title={`预览: ${preview.name}`} action={<button onClick={() => setPreview(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--text-muted)' }}>关闭</button>} />
              <div style={{ overflow: 'auto', maxHeight: 300 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead><tr>
                    {preview.columns?.map((c: any) => <th key={c.name} style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: 'var(--text-secondary)', background: 'var(--bg-tertiary)', borderBottom: '2px solid var(--border)', whiteSpace: 'nowrap' }}>{c.name}</th>)}
                  </tr></thead>
                  <tbody>
                    {preview.preview_rows.slice(0, 50).map((row: any, i: number) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border-light)' }}>
                        {preview.columns?.map((c: any) => <td key={c.name} style={{ padding: '6px 12px', color: 'var(--text-primary)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{String(row[c.name] ?? '')}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {analysis && (
            <Card>
              <CardHeader title={`分析结果: ${analysis.name || ''}`} action={<button onClick={() => setAnalysis(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--text-muted)' }}>关闭</button>} />
              <div style={{ padding: 16 }}>
                <AnalysisResultView analysis={analysis} />
              </div>
            </Card>
          )}
        </div>
      )}
    </>
  )
}
