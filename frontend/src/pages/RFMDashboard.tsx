import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { API_BASE, fetchDatasets, getToken } from '../api'

interface RFMData { summary: { users: number; orders: number; ref_date: string }; means: { R: number; F: number; M: number }; segments: { label: string; count: number; amount: number; count_pct: string; amount_pct: string; color: string }[]; chart_html: string }

export default function RFMDashboard() {
  const [searchParams] = useSearchParams()
  const dsId = searchParams.get('dataset_id')
  const [datasets, setDatasets] = useState<any[]>([])
  const [datasetId, setDatasetId] = useState(dsId || '')
  const [data, setData] = useState<RFMData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { fetchDatasets().then((d: any) => { if (Array.isArray(d)) setDatasets(d) }).catch(() => {}) }, [])

  const runRFM = async (id?: string) => {
    if (id) setDatasetId(id)
    setLoading(true); setError(''); setData(null)
    try {
      const body = id ? JSON.stringify({ dataset_id: Number(id) }) : '{}'
      const res = await fetch(`${API_BASE}/analysis/rfm`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body,
      })
      if (!res.ok) { const t = await res.text(); setError(t); setLoading(false); return }
      setData(await res.json())
    } catch (e: any) { setError(e.message || 'Network error') }
    setLoading(false)
  }

  useEffect(() => { dsId ? runRFM(dsId) : runRFM() }, [dsId])

  return (
    <div style={{ minHeight: '100vh', background: '#1a1a2e' }}>
      <header style={{ padding: '12px 24px', display: 'flex', alignItems: 'center', gap: 16, background: '#16213e', borderBottom: '1px solid #0f3460' }}>
        <Link to="/" style={{ color: '#e94560', textDecoration: 'none', fontSize: 13 }}>{'<- Back'}</Link>
        <span style={{ fontSize: 18, fontWeight: 700, color: '#fff' }}>RFM Customer Analysis</span>
        <div style={{ flex: 1 }} />
        <select value={datasetId} onChange={(e) => runRFM(e.target.value)}
          style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid #0f3460', fontSize: 13, background: '#0f3460', color: '#eaeaea', outline: 'none' }}>
          <option value="">Default file</option>
          {datasets.map((d: any) => <option key={d.id} value={String(d.id)}>{d.name}</option>)}
        </select>
      </header>

      {loading && <div style={{ padding: 40, textAlign: 'center', color: '#eaeaea', fontSize: 14 }}>Analyzing...</div>}
      {error && <div style={{ margin: 20, padding: 12, background: '#e9456020', borderRadius: 6, color: '#e94560', fontSize: 13 }}>{error}</div>}

      {data && (
        <div>
          {/* Stat cards */}
          <div style={{ display: 'flex', gap: 12, padding: '16px 24px' }}>
            {[
              { label: 'Users', value: data.summary.users, color: '#e94560' },
              { label: 'Orders', value: data.summary.orders, color: '#0f3460' },
              { label: 'R Mean', value: data.means.R + 'd', color: '#533483' },
              { label: 'F Mean', value: data.means.F + 'x', color: '#1a73e8' },
              { label: 'M Mean', value: '\xA5' + data.means.M.toLocaleString(), color: '#0d904f' },
            ].map((c) => (
              <div key={c.label} style={{ flex: 1, background: '#16213e', borderRadius: 10, border: `1px solid ${c.color}44`, padding: '12px 16px', textAlign: 'center' }}>
                <div style={{ fontSize: 22, fontWeight: 700, color: c.color }}>{c.value}</div>
                <div style={{ fontSize: 11, color: '#8892b0', marginTop: 2 }}>{c.label}</div>
              </div>
            ))}
          </div>

          {/* 3D scatter + Segments */}
          <div style={{ display: 'flex', gap: 12, padding: '0 24px', height: 480 }}>
            <div style={{ flex: 1, background: '#16213e', borderRadius: 10, border: '1px solid #0f3460', overflow: 'hidden' }}>
              <iframe src={`${data.chart_html}?token=${getToken()}`} style={{ width: '100%', height: '100%', border: 'none' }} />
            </div>

            <div style={{ width: 240, flexShrink: 0, background: '#16213e', borderRadius: 10, border: '1px solid #0f3460', padding: 12, overflow: 'auto' }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#eaeaea', marginBottom: 8 }}>Segments</div>
              {data.segments.map((s) => (
                <div key={s.label} style={{ padding: '6px 8px', borderRadius: 6, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8, background: s.color + '18' }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: s.color, flexShrink: 0 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, color: '#eaeaea', fontWeight: 500 }}>{s.label}</div>
                    <div style={{ fontSize: 10, color: '#8892b0' }}>{s.count}p / {(s.amount / 10000).toFixed(1)}w</div>
                  </div>
                  <span style={{ fontSize: 11, color: s.color, fontWeight: 600 }}>{s.count_pct}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {!data && !loading && !error && (
        <div style={{ padding: 60, textAlign: 'center', color: '#8892b0', fontSize: 14 }}>
          Select a dataset or use the default file to start analysis.
        </div>
      )}
    </div>
  )
}
