import { useState, useEffect, useMemo } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { Spinner, ErrorMsg, Card, CardHeader, headers, API_BASE } from './shared'

const CHART_BLUE = '#42a5f5'
const CHART_GREEN = '#4caf50'
const CHART_RED = '#ef5350'

/* KPI 卡片（可带环比趋势：↑绿 / ↓红） */
function StatCard({ label, value, color, trend }: {
  label: string; value: string | number; color: string; trend?: { text: string; up: boolean }
}) {
  return (
    <div className="stat-card" style={{
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
          background: trend.up ? `${CHART_GREEN}18` : `${CHART_RED}18`,
          color: trend.up ? CHART_GREEN : CHART_RED, alignSelf: 'center',
        }}>
          {trend.up ? '↑' : '↓'} {trend.text}
        </div>
      )}
    </div>
  )
}

export default function DashboardTab({ isAdmin }: { isAdmin: boolean }) {
  const [data, setData] = useState<any>(null)
  const [agents, setAgents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = () => {
    Promise.all([
      fetch(`${API_BASE}/admin/dashboard`, { headers: headers() })
        .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
        .then((d) => { setData(d); setError('') })
        .catch((e) => setError(`仪表盘加载失败: ${e.message}`)),
      fetch(`${API_BASE}/admin/agent-status`, { headers: headers() })
        .then((r) => { if (!r.ok) throw new Error(); return r.json() })
        .then((d) => { if (Array.isArray(d)) setAgents(d) })
        .catch(() => {}),
    ]).finally(() => setLoading(false))
  }

  useEffect(() => { load(); const i = setInterval(load, 15000); return () => clearInterval(i) }, [])

  /* 补齐最近 30 天完整序列（后端只返回有消息的日期，缺 0 的天数会断档） */
  const chartData = useMemo(() => {
    if (!data?.daily_messages?.length) return []
    const byDate: Record<string, number> = {}
    data.daily_messages.forEach((d: any) => { byDate[d.date] = d.count })
    const days: { label: string; count: number }[] = []
    const today = new Date()
    for (let i = 29; i >= 0; i--) {
      const d = new Date(today)
      d.setDate(today.getDate() - i)
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      days.push({
        label: `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`,
        count: byDate[key] || 0,
      })
    }
    return days
  }, [data])

  /* 趋势计算：今日 vs 昨日、近7天 vs 前7天 */
  const trends = useMemo(() => {
    const total = chartData.reduce((s, d) => s + d.count, 0)
    const last7 = chartData.slice(-7).reduce((s, d) => s + d.count, 0)
    const prev7 = chartData.slice(-14, -7).reduce((s, d) => s + d.count, 0)
    const today = chartData[chartData.length - 1]?.count ?? 0
    const yesterday = chartData[chartData.length - 2]?.count ?? 0
    const pct = (cur: number, base: number) =>
      base > 0 ? Math.round(((cur - base) / base) * 100) : (cur > 0 ? 100 : 0)
    return {
      total,
      todayVsYesterday: pct(today, yesterday),
      week7: pct(last7, prev7),
    }
  }, [chartData])

  const onlineCount = agents.filter((a: any) => a.online).length
  const allCards = [
    { label: '用户数', value: data?.users ?? '-', color: '#42a5f5', adminOnly: true, trend: null as null | { text: string; up: boolean } },
    { label: '会话数', value: data?.sessions ?? '-', color: '#66bb6a', adminOnly: true, trend: null as null | { text: string; up: boolean } },
    {
      label: '消息数', value: data?.messages ?? '-', color: '#ffa726', adminOnly: true,
      trend: chartData.length > 0 ? {
        text: `近7天 ${Math.abs(trends.week7)}%`, up: trends.week7 >= 0,
      } : null,
    },
    { label: '在线 Agent', value: onlineCount, color: '#26c6da', adminOnly: false, trend: null as null | { text: string; up: boolean } },
    {
      label: '今日消息', value: data?.today_messages ?? '-', color: '#ef5350', adminOnly: false,
      trend: chartData.length > 0 ? {
        text: `较昨日 ${Math.abs(trends.todayVsYesterday)}%`, up: trends.todayVsYesterday >= 0,
      } : null,
    },
    { label: '今日活跃会话', value: data?.today_users ?? '-', color: '#ab47bc', adminOnly: false, trend: null as null | { text: string; up: boolean } },
    { label: '均消息/会话', value: data?.avg_messages ?? '-', color: '#26a69a', adminOnly: true, trend: null as null | { text: string; up: boolean } },
    { label: '数据集', value: data?.datasets ?? '-', color: '#8d6e63', adminOnly: false, trend: null as null | { text: string; up: boolean } },
  ]
  const cards = isAdmin ? allCards : allCards.filter((c) => !c.adminOnly)

  return (
    <div>
      {error && <ErrorMsg msg={error} onRetry={load} />}
      {loading && <Spinner />}
      {!loading && <>
      {/* KPI 卡片 */}
      <div className="card-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 12, marginBottom: 24 }}>
        {cards.map((c) => (
          <StatCard key={c.label} label={c.label} value={c.value} color={c.color} trend={c.trend ?? undefined} />
        ))}
      </div>

      {/* 近30天消息量（补零完整轴） */}
      {isAdmin && chartData.length > 0 && (
        <Card style={{ marginBottom: 24, padding: '20px 24px' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px', color: 'var(--text-primary)' }}>近30天消息量</h3>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="dashMsgGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={CHART_BLUE} stopOpacity={0.35} />
                  <stop offset="95%" stopColor={CHART_BLUE} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} interval={4} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} allowDecimals={false} />
              <Tooltip
                cursor={{ stroke: 'var(--border)' }}
                content={({ active, payload }: any) => {
                  if (!active || !payload?.length) return null
                  const d = payload[0]?.payload
                  return (
                    <div style={{
                      background: 'var(--bg-primary)', border: '1px solid var(--border)',
                      borderRadius: 8, padding: '8px 12px', fontSize: 12, color: 'var(--text-primary)',
                    }}>
                      <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>{d.label}</div>
                      <div style={{ color: CHART_BLUE, fontWeight: 600 }}>消息 {d.count} 条</div>
                    </div>
                  )
                }}
              />
              <Area type="monotone" dataKey="count" stroke={CHART_BLUE} strokeWidth={2} fill="url(#dashMsgGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Agent 在线状态 */}
      {agents.length > 0 && (
        <Card>
          <CardHeader title="Agent 在线状态" />
          {agents.map((a: any) => (
            <div key={a.agent_id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 20px', borderBottom: '1px solid var(--border-light)' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: a.online ? 'var(--success)' : 'var(--text-muted)', flexShrink: 0, boxShadow: a.online ? '0 0 6px rgba(76,175,80,0.5)' : undefined }} />
              <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{a.agent_name}</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>ID: {a.agent_id}</span>
              <div style={{ flex: 1 }} />
              <span style={{ fontSize: 11, color: a.online ? 'var(--success)' : 'var(--text-muted)' }}>{a.online ? '在线' : '离线'}</span>
              {a.last_heartbeat && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.last_heartbeat}</span>}
            </div>
          ))}
        </Card>
      )}
      </>}
    </div>
  )
}
