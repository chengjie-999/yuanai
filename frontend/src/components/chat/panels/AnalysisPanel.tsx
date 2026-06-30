import { useState, useEffect } from 'react'
import { API_BASE, fetchDatasets, fetchDatasetAnalysis } from '../../../api'

export default function AnalysisPanel() {
  const [datasets, setDatasets] = useState<any[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [analysis, setAnalysis] = useState<any>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchDatasets().then((d: any) => { if (Array.isArray(d)) setDatasets(d) }).catch(() => {})
  }, [])

  const handleAnalyze = async (id: number) => {
    setSelectedId(id); setAnalyzing(true); setError(''); setAnalysis(null)
    try {
      const d = await fetchDatasetAnalysis(id, true, true)
      if (d) setAnalysis(d)
      else setError('分析失败')
    } catch { setError('分析失败') }
    setAnalyzing(false)
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0', flexShrink: 0 }}>
        <select
          value={selectedId ?? ''}
          onChange={(e) => { const v = Number(e.target.value); if (v) handleAnalyze(v) }}
          style={{
            width: '100%', padding: '6px 10px', borderRadius: 6,
            border: '1px solid var(--border)', fontSize: 13, outline: 'none',
            background: 'var(--bg-input)', color: 'var(--text-primary)',
          }}
        >
          <option value="">选择数据集分析...</option>
          {datasets.map((d: any) => (
            <option key={d.id} value={d.id}>{d.name} ({d.file_type})</option>
          ))}
        </select>
        {datasets.length === 0 && (
          <div style={{ fontSize: 12, color: '#ccc', textAlign: 'center', marginTop: 8 }}>
            暂无数据集，请先上传
          </div>
        )}
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '8px 14px' }}>
        {error && <div style={{ padding: 8, color: '#e53935', fontSize: 12 }}>{error}</div>}
        {analyzing && (
          <div style={{ textAlign: 'center', color: '#999', padding: 20, fontSize: 13 }}>分析中...</div>
        )}
        {analysis && (
          <div>
            {analysis.summary && (
              <div style={{ marginBottom: 12 }}>
                {Object.entries(analysis.summary).map(([k, v]: [string, any]) => {
                  let val = '-'
                  if (typeof v === 'number') {
                    val = Number.isInteger(v) ? String(v) : v.toFixed(2)
                  } else if (typeof v === 'object') {
                    val = JSON.stringify(v)
                  } else {
                    val = String(v)
                  }
                  return (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #f5f5f5', fontSize: 12 }}>
                      <span style={{ color: '#888' }}>{k}</span>
                      <span style={{ color: '#333', fontWeight: 500, textAlign: 'right', maxWidth: '60%', overflow: 'hidden', textOverflow: 'ellipsis' }}>{val}</span>
                    </div>
                  )
                })}
              </div>
            )}
            {analysis.text && (
              <div style={{ fontSize: 12, color: '#555', lineHeight: 1.6, marginBottom: 12, whiteSpace: 'pre-wrap' }}>
                {analysis.text}
              </div>
            )}
            {analysis.charts?.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {analysis.charts.map((name: string, i: number) => (
                  <img key={i} src={`${API_BASE}/data/analysis-image/${analysis.dataset_id}/${name}`}
                    alt={name}
                    style={{ width: '100%', borderRadius: 8, border: '1px solid var(--border)' }} />
                ))}
              </div>
            )}
          </div>
        )}
        {!selectedId && !analysis && (
          <div style={{ textAlign: 'center', color: '#ccc', padding: 40, fontSize: 13 }}>
            选择数据集开始分析
          </div>
        )}
      </div>
    </div>
  )
}
