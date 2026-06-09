import { useState, useEffect } from 'react'
import { Spinner, Empty, ErrorMsg, Card, CardHeader, btnDangerSm, headers, API_BASE } from './shared'

export default function DatasetsTab() {
  const [datasets, setDatasets] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [preview, setPreview] = useState<any>(null)
  const [analysis, setAnalysis] = useState<any>(null)
  const [analyzing, setAnalyzing] = useState(false)

  const load = () => {
    setError('')
    fetch(`${API_BASE}/data/datasets`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((d) => { if (Array.isArray(d)) setDatasets(d) })
      .catch(() => setError('加载数据集失败'))
    setLoading(false)
  }
  useEffect(() => { load() }, [])

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
      {loading ? <Spinner /> : datasets.length === 0 ? <Empty msg="暂无数据集" /> : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Card>
            <CardHeader title={`数据集 (${datasets.length})`} />
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead><tr style={{ background: '#f5f5f8' }}>
                {['名称', '类型', '大小', '行数', '上传时间', '操作'].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600, borderBottom: '2px solid #e0e0e0' }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {datasets.map((d: any) => (
                  <tr key={d.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 600, color: '#333', cursor: 'pointer' }} onClick={() => setPreview(d)}>{d.name}</td>
                    <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{d.file_type}</td>
                    <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{d.file_size ? `${(d.file_size / 1024).toFixed(1)} KB` : '-'}</td>
                    <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{d.row_count ?? '-'}</td>
                    <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{d.create_time?.slice(0, 16)}</td>
                    <td style={{ padding: '10px 14px', display: 'flex', gap: 6 }}>
                      <button onClick={() => handleAnalyze(d.id)} disabled={analyzing} style={{ fontSize: 12, padding: '4px 10px', color: '#1976d2', border: '1px solid #1976d2', background: 'none', borderRadius: 4, cursor: 'pointer' }}>{analyzing ? '分析中...' : '分析'}</button>
                      <button onClick={() => handleDelete(d.id)} style={btnDangerSm}>删除</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          {preview && preview.preview_rows && (
            <Card>
              <CardHeader title={`预览: ${preview.name}`} action={<button onClick={() => setPreview(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: '#999' }}>关闭</button>} />
              <div style={{ overflow: 'auto', maxHeight: 300 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead><tr>
                    {preview.columns?.map((c: any) => <th key={c.name} style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: '#666', background: '#f5f5f8', borderBottom: '2px solid #e0e0e0', whiteSpace: 'nowrap' }}>{c.name}</th>)}
                  </tr></thead>
                  <tbody>
                    {preview.preview_rows.slice(0, 50).map((row: any, i: number) => (
                      <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
                        {preview.columns?.map((c: any) => <td key={c.name} style={{ padding: '6px 12px', color: '#333', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{String(row[c.name] ?? '')}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {analysis && (
            <Card>
              <CardHeader title={`分析结果: ${analysis.dataset_name || ''}`} action={<button onClick={() => setAnalysis(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: '#999' }}>关闭</button>} />
              <div style={{ padding: 16 }}>
                {analysis.summary && Object.entries(analysis.summary).map(([k, v]: [string, any]) => {
                  let val = '-'
                  if (typeof v === 'number') {
                    val = Number.isInteger(v) ? String(v) : v.toFixed(2)
                  } else if (typeof v === 'object') {
                    val = JSON.stringify(v)
                  } else {
                    val = String(v)
                  }
                  return (
                    <div key={k} style={{ display: 'flex', padding: '6px 0', borderBottom: '1px solid #f5f5f5' }}>
                      <span style={{ fontWeight: 600, fontSize: 13, color: '#333', minWidth: 160 }}>{k}</span>
                      <span style={{ fontSize: 13, color: '#666' }}>{val}</span>
                    </div>
                  )
                })}
                {analysis.text && <pre style={{ marginTop: 12, background: '#f5f5f8', borderRadius: 8, padding: 16, fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{analysis.text}</pre>}
                {analysis.charts?.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 16 }}>
                    {analysis.charts.map((name: string, i: number) => (
                      <img key={i} src={`${API_BASE}/data/analysis-image/${analysis.dataset_id}/${name}`} alt={name} style={{ maxWidth: '100%', borderRadius: 8, border: '1px solid #eee' }} />
                    ))}
                  </div>
                )}
              </div>
            </Card>
          )}
        </div>
      )}
    </>
  )
}
