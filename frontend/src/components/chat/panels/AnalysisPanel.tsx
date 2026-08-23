import { useState, useEffect, useRef } from 'react'
import { fetchDatasets, fetchDatasetAnalysis, uploadDataset, API_BASE } from '../../../api'
import AnalysisResultView from '../../AnalysisResultView'

export default function AnalysisPanel() {
  const [datasets, setDatasets] = useState<any[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [analysis, setAnalysis] = useState<any>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const loadDatasets = () => {
    fetchDatasets().then((d: any) => { if (Array.isArray(d)) setDatasets(d) }).catch(() => {})
  }
  useEffect(() => { loadDatasets() }, [])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true); setError('')
    const r = await uploadDataset(file)
    if (r?.id) {
      loadDatasets()
      setSelectedId(r.id)
      handleAnalyze(r.id)
    } else {
      setError(r?.detail || '上传失败')
    }
    setUploading(false)
    if (fileRef.current) fileRef.current.value = ''
  }

  const handleAnalyze = async (id: number) => {
    setSelectedId(id); setAnalyzing(true); setError(''); setAnalysis(null)
    try {
      const d = await fetchDatasetAnalysis(id, true, true)
      if (d) setAnalysis(d)
      else setError('分析失败')
    } catch { setError('分析失败') }
    setAnalyzing(false)
  }

  // 导出报告：后端接口需 JWT 鉴权（window.open 不带 token 会 401），
  // 用 fetch 带 Authorization 头拉取 blob 再触发浏览器下载
  const [exporting, setExporting] = useState(false)
  const [tip, setTip] = useState('')

  const handleExport = async () => {
    if (!selectedId) return
    setExporting(true)
    setTip('')
    try {
      const token = localStorage.getItem('token')
      const h: Record<string, string> = {}
      if (token) h['Authorization'] = `Bearer ${token}`
      const res = await fetch(`${API_BASE}/data/export/${selectedId}?format=excel`, { headers: h })
      if (!res.ok) {
        let detail = ''
        try { detail = (await res.json())?.detail || '' } catch { /* 非 JSON 错误响应 */ }
        setTip(detail || `导出失败 (HTTP ${res.status})`)
      } else {
        const blob = await res.blob()
        // 优先解析 Content-Disposition 中的文件名，缺失则按数据集名拼接
        let filename = ''
        const cd = res.headers.get('Content-Disposition') || ''
        const m = cd.match(/filename="?([^"]+)"?/)
        if (m) filename = m[1]
        if (!filename) {
          const ds = datasets.find((d: any) => d.id === selectedId)
          filename = `${(ds?.name || '数据集').replace(/\.[^.]+$/, '')}_分析报告.xlsx`
        }
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = filename
        document.body.appendChild(a)
        a.click()
        a.remove()
        URL.revokeObjectURL(url)
        setTip('导出成功')
      }
    } catch {
      setTip('导出失败，请重试')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border-light)', flexShrink: 0 }}>
        <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls,.json" onChange={handleUpload} style={{ display: 'none' }} />
        <div style={{ display: 'flex', gap: 6 }}>
          <select
            value={selectedId ?? ''}
            onChange={(e) => { const v = Number(e.target.value); if (v) handleAnalyze(v) }}
            style={{
              flex: 1, padding: '6px 10px', borderRadius: 6,
              border: '1px solid var(--border)', fontSize: 13, outline: 'none',
              background: 'var(--bg-input)', color: 'var(--text-primary)',
            }}
          >
            <option value="">选择数据集分析...</option>
            {datasets.map((d: any) => (
              <option key={d.id} value={d.id}>{d.name} ({d.file_type})</option>
            ))}
          </select>
          <button onClick={() => fileRef.current?.click()} disabled={uploading}
            style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-secondary)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 12, whiteSpace: 'nowrap' }}>
            {uploading ? '上传中...' : '📤 上传'}
          </button>
          <button onClick={handleExport} disabled={!selectedId || exporting}
            style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-secondary)', color: selectedId ? 'var(--accent)' : 'var(--text-muted)', cursor: selectedId && !exporting ? 'pointer' : 'not-allowed', fontSize: 12, whiteSpace: 'nowrap' }}>
            {exporting ? '导出中...' : '⬇ 导出'}
          </button>
        </div>
        {tip && (
          <div style={{ fontSize: 12, marginTop: 6, textAlign: 'center', color: tip === '导出成功' ? '#629755' : 'var(--danger)' }}>
            {tip}
          </div>
        )}
        {datasets.length === 0 && (
          <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', marginTop: 8 }}>
            暂无数据集，上传 CSV / Excel / JSON 开始分析
          </div>
        )}
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '8px 14px' }}>
        {error && <div style={{ padding: 8, color: 'var(--danger)', fontSize: 12 }}>{error}</div>}
        {analyzing && (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 20, fontSize: 13 }}>分析中...</div>
        )}
        {analysis && <AnalysisResultView analysis={analysis} />}
        {!selectedId && !analysis && (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 40, fontSize: 13 }}>
            选择数据集或上传文件开始分析
          </div>
        )}
      </div>
    </div>
  )
}
