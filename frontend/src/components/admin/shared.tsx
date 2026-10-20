import { useState, useEffect } from 'react'
import { headers } from '../../api'
import { TrendingUpIcon, TrendingDownIcon } from '../icons'

export { ErrorBoundary } from '../ErrorBoundary'

export function useAdminFetch<T>(url: string) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = () => {
    setError('')
    fetch(url, { headers: headers() })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => { setData(d); setError('') })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])
  return { data, loading, error, reload: load }
}

export const Spinner = () => <div style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: 40, fontSize: 13 }}>加载中...</div>

export const Empty = ({ msg = '暂无数据' }: { msg?: string }) => <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 40, fontSize: 13 }}>{msg}</div>

export const ErrorMsg = ({ msg, onRetry }: { msg: string; onRetry?: () => void }) => (
  <div style={{ color: 'var(--danger)', fontSize: 13, padding: 12, background: 'var(--accent-light)', borderRadius: 8, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
    <span style={{ flex: 1 }}>{msg}</span>
    {onRetry && <button onClick={onRetry} title="重试" aria-label="重试" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--accent)', fontSize: 12, whiteSpace: 'nowrap' }}>重试</button>}
  </div>
)

export const Card = ({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) => (
  <div style={{ background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden', ...style }}>{children}</div>
)

export const CardHeader = ({ title, action }: { title: string; action?: React.ReactNode }) => (
  <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border-light)', fontWeight: 600, fontSize: 14, color: 'var(--text-primary)', background: 'var(--bg-secondary)', display: 'flex', alignItems: 'center' }}>
    {title}<div style={{ flex: 1 }} />{action}
  </div>
)

export const btnPrimary: React.CSSProperties = { background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 6, padding: '7px 16px', cursor: 'pointer', fontSize: 13, fontWeight: 500 }
export const btnDangerSm: React.CSSProperties = { fontSize: 12, padding: '4px 10px', color: 'var(--danger)', border: '1px solid var(--danger)', background: 'none', borderRadius: 4, cursor: 'pointer' }
export const inputStyle: React.CSSProperties = { padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 13, outline: 'none', boxSizing: 'border-box', background: 'var(--bg-input)', color: 'var(--text-primary)' }
export const badge = (text: string, color: string) => <span style={{ fontSize: 11, color, background: `color-mix(in srgb, ${color} 10%, transparent)`, padding: '2px 6px', borderRadius: 4, marginLeft: 6 }}>{text}</span>

/* KPI 统计卡（2026-10-21 清洁9：AnalyticsTabs/DashboardTab/UserAnalyticsTab
   三份本地拷贝合一；trend 环比徽标用语义色变量） */
export const StatCard = ({ label, value, color, sub, trend }: {
  label: string; value: string | number; color: string; sub?: string
  trend?: { text: string; up: boolean }
}) => (
  <div style={{
    background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)',
    padding: '14px 12px', textAlign: 'center', transition: 'box-shadow 0.2s',
    display: 'flex', flexDirection: 'column', gap: 4,
  }}
    onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 2px 12px var(--shadow-sm)')}
    onMouseLeave={(e) => (e.currentTarget.style.boxShadow = '')}>
    <div style={{ fontSize: 24, fontWeight: 700, color, lineHeight: 1.3 }}>{value}</div>
    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{label}</div>
    {trend && (
      <div style={{
        fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 8,
        background: trend.up ? 'var(--success-soft)' : 'var(--danger-soft)',
        color: trend.up ? 'var(--success)' : 'var(--danger)', alignSelf: 'center',
        display: 'flex', alignItems: 'center', gap: 3, lineHeight: 1,
      }}>
        {trend.up ? <TrendingUpIcon size={11} /> : <TrendingDownIcon size={11} />}
        {trend.text}
      </div>
    )}
    {sub && <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{sub}</div>}
  </div>
)

export { headers, safeJson, API_BASE } from '../../api'
