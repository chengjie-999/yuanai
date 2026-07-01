import { useState, useEffect } from 'react'
import { API_BASE, fetchDatasets, fetchDatasetAnalysis } from '../../../api'
import AnalysisResultView from '../../AnalysisResultView'

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
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border-light)', flexShrink: 0 }}>
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
          <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', marginTop: 8 }}>
            暂无数据集，请先上传
          </div>
        )}
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '8px 14px' }}>
        {error && <div style={{ padding: 8, color: 'var(--danger)', fontSize: 12 }}>{error}</div>}
        {analyzing && (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 20, fontSize: 13 }}>分析中...</div>
        )}
        {analysis && <AnalysisResult analysis={analysis} />}
        {!selectedId && !analysis && (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 40, fontSize: 13 }}>
            选择数据集开始分析
          </div>
        )}
      </div>
    </div>
  )
}
