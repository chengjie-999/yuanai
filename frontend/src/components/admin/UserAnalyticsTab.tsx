/* 用户行为分析 — 用户维度指标体系（L1 流量 / L2 页面价值 / L3 用户活跃 / L4 转化漏斗）

数据源：visit_log（路由级埋点，登录用户带 uid）+ users/chat_session 关联
口径：
- PV/UV：IP 去重；登录用户 PV 占比 = 转化漏斗第一环
- 页面排行：哪个功能有人用 → 定价依据
- 活跃分层：近 30 天访问天数——高活≥15 / 中活7-14 / 低活1-6 / 流失0
*/
import { useState, useEffect, useMemo } from 'react'
import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'
import { Spinner, ErrorMsg, Card, StatCard, headers, API_BASE } from './shared'

const C_HIGH = '#4caf50'
const C_MID = '#42a5f5'
const C_LOW = '#ffa726'
const C_CHURN = '#9e9e9e'
const C_LOGIN = '#7b1fa2'

export default function UserAnalyticsTab() {
  const [data, setData] = useState<any>(null)
  const [days, setDays] = useState(30)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  // 2026-10-19 修复：重试此前 setDays(d=>d) 同值 React bail out 不发请求；
  // 用 reload 计数作为 effect 依赖，重试 +1 重新拉取
  const [reload, setReload] = useState(0)

  useEffect(() => {
    setLoading(true); setError('')
    fetch(`${API_BASE}/admin/user-analytics?days=${days}`, { headers: headers() })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((d) => setData(d))
      .catch((e) => setError(`用户分析加载失败: ${e.message}`))
      .finally(() => setLoading(false))
  }, [days, reload])

  const trend = useMemo(() => {
    if (!data?.daily?.length) return []
    const byDate: Record<string, { pv: number; uv: number }> = {}
    data.daily.forEach((d: any) => { byDate[d.date] = { pv: d.pv, uv: d.uv } })
    const out: { label: string; pv: number; uv: number }[] = []
    const today = new Date()
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(today)
      d.setDate(today.getDate() - i)
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      out.push({ label: key.slice(5), ...(byDate[key] || { pv: 0, uv: 0 }) })
    }
    return out
  }, [data, days])

  const segChart = data?.segments ? [
    { name: '高活(≥15天)', v: data.segments.high, c: C_HIGH },
    { name: '中活(7-14天)', v: data.segments.mid, c: C_MID },
    { name: '低活(1-6天)', v: data.segments.low, c: C_LOW },
    { name: '流失(0天)', v: data.segments.churned, c: C_CHURN },
  ] : []

  if (loading) return <Spinner />
  if (error) return <ErrorMsg msg={error} onRetry={() => setReload((n) => n + 1)} />

  const ov = data?.overview || {}

  return (
    <div>
      {/* 时间窗 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {[7, 30, 90].map((n) => (
          <button key={n} onClick={() => setDays(n)}
            style={{
              padding: '5px 16px', borderRadius: 16, fontSize: 12.5, cursor: 'pointer',
              border: `1px solid ${days === n ? 'var(--accent)' : 'var(--border)'}`,
              background: days === n ? 'var(--accent)' : 'var(--bg-primary)',
              color: days === n ? '#fff' : 'var(--text-secondary)', fontWeight: 600,
            }}>
            近{n}天
          </button>
        ))}
      </div>

      {/* L1 流量 KPI */}
      <div className="card-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 12, marginBottom: 24 }}>
        <StatCard label={`近${days}天 PV`} value={(ov.period?.pv ?? 0).toLocaleString()} color="#42a5f5" />
        <StatCard label={`近${days}天 UV`} value={(ov.period?.uv ?? 0).toLocaleString()} color="#4caf50" />
        <StatCard label="登录用户 PV 占比" value={`${ov.period?.login_ratio ?? 0}%`} color={C_LOGIN}
          sub="获客 → 激活漏斗第一环" />
        <StatCard label="今日 PV" value={ov.today?.pv ?? 0} color="#26c6da" />
        <StatCard label="今日 UV" value={ov.today?.uv ?? 0} color="#26a69a" />
      </div>

      {/* L1 趋势 */}
      {trend.length > 0 && (
        <Card style={{ marginBottom: 24, padding: '20px 24px' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px', color: 'var(--text-primary)' }}>PV / UV 趋势（近{days}天）</h3>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={trend} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="uaPvGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#42a5f5" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#42a5f5" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="label" fontSize={10} stroke="var(--text-muted)" tickLine={false} axisLine={false} />
              <YAxis fontSize={10} stroke="var(--text-muted)" tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
              <Area type="monotone" dataKey="pv" name="PV" stroke="#42a5f5" strokeWidth={2} fill="url(#uaPvGrad)" />
              <Area type="monotone" dataKey="uv" name="UV" stroke="#4caf50" strokeWidth={2} fill="transparent" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 16 }}>
        {/* L2 页面价值排行 */}
        <Card style={{ padding: '20px 24px' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 4px', color: 'var(--text-primary)' }}>页面访问排行（近{days}天）</h3>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>哪个功能有人用 → 定价与迭代依据</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
                <th style={{ padding: '6px 6px', borderBottom: '1px solid var(--border)' }}>页面</th>
                <th style={{ padding: '6px 6px', borderBottom: '1px solid var(--border)', textAlign: 'right' }}>PV</th>
                <th style={{ padding: '6px 6px', borderBottom: '1px solid var(--border)', textAlign: 'right' }}>UV</th>
                <th style={{ padding: '6px 6px', borderBottom: '1px solid var(--border)', textAlign: 'right' }}>登录 PV</th>
              </tr>
            </thead>
            <tbody>
              {(data?.pages || []).map((p: any) => (
                <tr key={p.path} style={{ color: 'var(--text-primary)' }}>
                  <td style={{ padding: '6px 6px', borderBottom: '1px solid var(--border-light)', fontFamily: 'monospace', fontSize: 11 }}>{p.path || '/'}</td>
                  <td style={{ padding: '6px 6px', borderBottom: '1px solid var(--border-light)', textAlign: 'right' }}>{p.pv}</td>
                  <td style={{ padding: '6px 6px', borderBottom: '1px solid var(--border-light)', textAlign: 'right' }}>{p.uv}</td>
                  <td style={{ padding: '6px 6px', borderBottom: '1px solid var(--border-light)', textAlign: 'right', color: C_LOGIN }}>{p.login_pv}</td>
                </tr>
              ))}
              {(data?.pages || []).length === 0 && (
                <tr><td colSpan={4} style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>暂无访问数据（埋点上线后积累）</td></tr>
              )}
            </tbody>
          </table>
        </Card>

        {/* L3 活跃分层 */}
        <Card style={{ padding: '20px 24px' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 4px', color: 'var(--text-primary)' }}>用户活跃分层（近{days}天访问天数）</h3>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>高活≥15天 / 中活7-14 / 低活1-6 / 流失0（含未访问账号）</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={segChart} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
              <XAxis type="number" fontSize={10} stroke="var(--text-muted)" tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="name" fontSize={11} stroke="var(--text-muted)" width={90} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="v" name="人数" radius={[0, 6, 6, 0]} barSize={18}>
                {segChart.map((s, i) => <Cell key={i} fill={s.c} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* L3 活跃用户排行 */}
      <Card style={{ marginTop: 16, padding: '20px 24px' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 4px', color: 'var(--text-primary)' }}>活跃用户排行（近{days}天）</h3>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>访问次数 / 活跃天数 / 会话数 / 消息数 / 最后活跃——谁是真用户</div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
              {['用户', '访问次数', '活跃天数', '会话数', '消息数', '最后活跃'].map((h) => (
                <th key={h} style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(data?.users || []).map((u: any) => (
              <tr key={u.user_id} style={{ color: 'var(--text-primary)' }}>
                <td style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-light)' }}>{u.username}</td>
                <td style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-light)' }}>{u.visits}</td>
                <td style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-light)' }}>{u.active_days}</td>
                <td style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-light)' }}>{u.sessions}</td>
                <td style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-light)' }}>{u.messages}</td>
                <td style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-light)' }}>{u.last_active}</td>
              </tr>
            ))}
            {(data?.users || []).length === 0 && (
              <tr><td colSpan={6} style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>暂无登录用户访问记录</td></tr>
            )}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
