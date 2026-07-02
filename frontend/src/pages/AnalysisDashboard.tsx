import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { API_BASE, getToken } from '../api'

export default function AnalysisDashboard() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!sessionId) return
    // try agent-cached data first, then fallback to direct RFM API
    fetch(API_BASE + '/analysis/dashboard/' + sessionId, {
      headers: { Authorization: 'Bearer ' + getToken() },
    })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json() })
      .then(setData)
      .catch(function () {
        // fallback: try direct RFM API
        return fetch(API_BASE + '/analysis/rfm', {
          method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + getToken() },
          body: '{}',
        }).then(function (r) { return r.ok ? r.json() : Promise.reject() })
          .then(setData)
          .catch(function () { setError('Dashboard data not available. Run RFM analysis in chat first.') })
      })
      .finally(function () { setLoading(false) })
  }, [sessionId])

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>Loading...</div>
  if (error) return <div style={{ padding: 60, textAlign: 'center' }}>
    <div style={{ fontSize: 40, marginBottom: 12, opacity: 0.3 }}>📊</div>
    <div style={{ color: 'var(--danger)', fontSize: 14, marginBottom: 8 }}>{error}</div>
    <Link to="/" style={{ color: 'var(--accent)', fontSize: 13 }}>Back to Chat</Link>
  </div>
  if (!data) return null

  var summary = data.summary, means = data.means, segments = data.segments, chart_html = data.chart_html
  var cards = []
  if (summary) {
    Object.keys(summary).forEach(function (k) { cards.push({ label: k, value: String(summary[k]) }) })
  }
  if (means) {
    Object.keys(means).forEach(function (k) { cards.push({ label: k, value: typeof means[k] === 'number' ? means[k].toLocaleString() : String(means[k]) }) })
  }

  var colors = ['#e94560', '#0f3460', '#533483', '#1a73e8', '#0d904f', '#f9a825']

  return (
    <div style={{ minHeight: '100vh', background: '#1a1a2e' }}>
      <header style={{ padding: '12px 24px', display: 'flex', alignItems: 'center', gap: 16, background: '#16213e', borderBottom: '1px solid #0f3460' }}>
        <Link to="/" style={{ color: '#e94560', textDecoration: 'none', fontSize: 13 }}>Back</Link>
        <span style={{ fontSize: 18, fontWeight: 700, color: '#fff' }}>Analysis Dashboard</span>
      </header>

      {cards.length > 0 && (
        <div style={{ display: 'flex', gap: 12, padding: '16px 24px', flexWrap: 'wrap' }}>
          {cards.map(function (c, i) {
            return (
              <div key={c.label} style={{ flex: '1 1 120px', minWidth: 100, background: '#16213e', borderRadius: 10, border: '1px solid ' + colors[i % colors.length] + '44', padding: '12px 16px', textAlign: 'center' }}>
                <div style={{ fontSize: 22, fontWeight: 700, color: colors[i % colors.length] }}>{c.value}</div>
                <div style={{ fontSize: 11, color: '#8892b0', marginTop: 2 }}>{c.label}</div>
              </div>
            )
          })}
        </div>
      )}

      {chart_html && (
        <div style={{ padding: '0 24px', height: 480 }}>
          <iframe src={chart_html + '?token=' + getToken()} style={{ width: '100%', height: '100%', border: 'none', borderRadius: 10 }} />
        </div>
      )}

      {segments && segments.length > 0 && (
        <div style={{ padding: '16px 24px' }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#eaeaea', marginBottom: 8 }}>Segments</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {segments.map(function (s: any) {
              return (
                <div key={s.label} style={{ padding: '8px 14px', borderRadius: 8, background: '#16213e', border: '1px solid ' + (s.color || '#333') + '44', minWidth: 120 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 2, background: s.color }} />
                    <span style={{ fontSize: 13, color: '#eaeaea', fontWeight: 500 }}>{s.label}</span>
                  </div>
                  <div style={{ fontSize: 11, color: '#8892b0' }}>{s.count} ({s.count_pct}) &middot; {s.amount_pct}</div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
