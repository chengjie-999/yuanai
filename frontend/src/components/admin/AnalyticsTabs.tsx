/* 多维度经营分析 — 对话 / 功能 / 留存 / 成本（盈利决策数据底座） */
import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'
import { Spinner, ErrorMsg, Card, headers, API_BASE } from './shared'

const C_BLUE = '#42a5f5'
const C_GREEN = '#4caf50'
const C_ORANGE = '#ffa726'
const C_RED = '#ef5350'

function StatCard({ label, value, color, sub }: { label: string; value: string | number; color: string; sub?: string }) {
  return (
    <div style={{ background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', padding: '14px 12px', textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ fontSize: 22, fontWeight: 700, color, lineHeight: 1.3 }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{label}</div>
      {sub && <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{sub}</div>}
    </div>
  )
}

function useAnalytics(scope: string, days: number) {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    setLoading(true); setError('')
    // 2026-10-19 修复：快速切换 7/30/90 天时旧响应可覆盖新数据——失效守卫
    let alive = true
    fetch(`${API_BASE}/admin/analytics/${scope}?days=${days}`, { headers: headers() })
      .then(async (r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then((d) => { if (alive) setData(d) })
      .catch((e) => { if (alive) setError(`${scope} 分析加载失败: ${e.message}`) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [scope, days])
  return { data, loading, error, setDays: () => {} }
}

function DaysSwitch({ days, setDays }: { days: number; setDays: (n: number) => void }) {
  return (
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
  )
}

const tooltipStyle = { background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }

/* ---------------- 对话分析 ---------------- */
export function ChatAnalyticsTab() {
  const [days, setDays] = useState(30)
  const { data, loading, error } = useAnalytics('chat', days)
  if (loading) return <Spinner />
  if (error) return <ErrorMsg msg={error} />
  const ov = data?.overview || {}
  return (
    <div>
      <DaysSwitch days={days} setDays={setDays} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 12, marginBottom: 24 }}>
        <StatCard label={`近${days}天消息`} value={ov.messages?.toLocaleString() ?? 0} color={C_BLUE} />
        <StatCard label="会话数" value={ov.sessions ?? 0} color={C_GREEN} />
        <StatCard label="均消息/会话" value={ov.avg_per_session ?? 0} color={C_ORANGE} sub="深度使用指标" />
        <StatCard label="长会话占比(≥10条)" value={`${ov.long_session_ratio ?? 0}%`} color="#7b1fa2" />
        <StatCard label="点赞率" value={`${ov.like_ratio ?? 0}%`} color={C_GREEN} sub={`赞${ov.likes ?? 0} / 踩${ov.dislikes ?? 0}（满意度）`} />
      </div>

      <Card style={{ marginBottom: 16, padding: '20px 24px' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px', color: 'var(--text-primary)' }}>消息量趋势（近{days}天）</h3>
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={data?.daily || []} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="chatGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={C_BLUE} stopOpacity={0.3} />
                <stop offset="95%" stopColor={C_BLUE} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="date" fontSize={10} stroke="var(--text-muted)" tickLine={false} axisLine={false} tickFormatter={(v) => String(v).slice(5)} />
            <YAxis fontSize={10} stroke="var(--text-muted)" tickLine={false} axisLine={false} />
            <Tooltip contentStyle={tooltipStyle} />
            <Area type="monotone" dataKey="messages" name="消息" stroke={C_BLUE} strokeWidth={2} fill="url(#chatGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </Card>

      <Card style={{ padding: '20px 24px' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px', color: 'var(--text-primary)' }}>活跃时段分布（24 小时）</h3>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={data?.hours || []} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis dataKey="hour" fontSize={10} stroke="var(--text-muted)" tickLine={false} axisLine={false} tickFormatter={(v) => `${v}时`} />
            <YAxis fontSize={10} stroke="var(--text-muted)" tickLine={false} axisLine={false} />
            <Tooltip contentStyle={tooltipStyle} />
            <Bar dataKey="count" name="消息数" fill={C_BLUE} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>
    </div>
  )
}

/* ---------------- 功能分析 ---------------- */
export function FeatureAnalyticsTab() {
  const [days, setDays] = useState(30)
  const { data, loading, error } = useAnalytics('features', days)
  if (loading) return <Spinner />
  if (error) return <ErrorMsg msg={error} />
  const feats = Object.entries(data?.features || {})
  return (
    <div>
      <DaysSwitch days={days} setDays={setDays} />
      <Card style={{ marginBottom: 16, padding: '20px 24px' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 4px', color: 'var(--text-primary)' }}>功能使用渗透率（近{days}天）</h3>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 16 }}>
          活跃用户 {data?.active_users ?? 0} 人；渗透率 = 使用该功能的用户数 / 活跃用户数 → 哪个功能值得收费
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={feats.map(([, v]: any) => ({ name: v.label, p: v.penetration }))} layout="vertical"
            margin={{ top: 4, right: 32, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
            <XAxis type="number" fontSize={10} stroke="var(--text-muted)" tickLine={false} axisLine={false} unit="%" />
            <YAxis type="category" dataKey="name" fontSize={12} stroke="var(--text-muted)" width={120} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={tooltipStyle} formatter={(v: any) => `${v}%`} />
            <Bar dataKey="p" name="渗透率" fill={C_GREEN} radius={[0, 6, 6, 0]} barSize={20} />
          </BarChart>
        </ResponsiveContainer>
      </Card>
      <Card style={{ padding: '20px 24px' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 12px', color: 'var(--text-primary)' }}>功能数据量</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
              {['功能', '总量', `近${days}天新增`, '使用用户数'].map((h) => (
                <th key={h} style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {feats.map(([, v]: any) => (
              <tr key={v.label} style={{ color: 'var(--text-primary)' }}>
                <td style={{ padding: '8px 8px', borderBottom: '1px solid var(--border-light)' }}>{v.label}</td>
                <td style={{ padding: '8px 8px', borderBottom: '1px solid var(--border-light)' }}>{v.total}</td>
                <td style={{ padding: '8px 8px', borderBottom: '1px solid var(--border-light)' }}>{v.recent}</td>
                <td style={{ padding: '8px 8px', borderBottom: '1px solid var(--border-light)' }}>{v.active_users}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}

/* ---------------- 留存分析 ---------------- */
export function RetentionAnalyticsTab() {
  const [days, setDays] = useState(90)
  const { data, loading, error } = useAnalytics('retention', days)
  if (loading) return <Spinner />
  if (error) return <ErrorMsg msg={error} />
  return (
    <div>
      <DaysSwitch days={days} setDays={setDays} />
      <Card style={{ marginBottom: 16, padding: '20px 24px' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px', color: 'var(--text-primary)' }}>注册趋势（近{days}天）</h3>
        <ResponsiveContainer width="100%" height={160}>
          <AreaChart data={data?.daily || []} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="regGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={C_GREEN} stopOpacity={0.3} />
                <stop offset="95%" stopColor={C_GREEN} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="date" fontSize={10} stroke="var(--text-muted)" tickLine={false} axisLine={false} tickFormatter={(v) => String(v).slice(5)} />
            <YAxis fontSize={10} stroke="var(--text-muted)" tickLine={false} axisLine={false} />
            <Tooltip contentStyle={tooltipStyle} />
            <Area type="monotone" dataKey="count" name="注册" stroke={C_GREEN} strokeWidth={2} fill="url(#regGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </Card>
      <Card style={{ padding: '20px 24px' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 4px', color: 'var(--text-primary)' }}>注册周留存矩阵</h3>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
          第 k 周留存 = 注册后第 k 周内回访的用户占比——**产品生死指标**（≥40% 健康，&lt;20% 危险）
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ color: 'var(--text-muted)' }}>
              <th style={{ padding: '8px', borderBottom: '1px solid var(--border)' }}>注册周</th>
              <th style={{ padding: '8px', borderBottom: '1px solid var(--border)' }}>注册数</th>
              {['第1周', '第2周', '第3周', '第4周'].map((h) => (
                <th key={h} style={{ padding: '8px', borderBottom: '1px solid var(--border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(data?.matrix || []).map((m: any) => (
              <tr key={m.week} style={{ color: 'var(--text-primary)' }}>
                <td style={{ padding: '8px', borderBottom: '1px solid var(--border-light)' }}>{m.week}</td>
                <td style={{ padding: '8px', borderBottom: '1px solid var(--border-light)' }}>{m.registered}</td>
                {['r1', 'r2', 'r3', 'r4'].map((k) => (
                  <td key={k} style={{
                    padding: '8px', borderBottom: '1px solid var(--border-light)',
                    background: m[k] >= 40 ? 'rgba(76,175,80,0.12)' : m[k] >= 20 ? 'rgba(255,167,38,0.12)' : 'rgba(239,83,80,0.08)',
                    color: m[k] >= 40 ? C_GREEN : m[k] >= 20 ? C_ORANGE : C_RED, fontWeight: 600,
                  }}>
                    {m[k] ? `${m[k]}%` : '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}

/* ---------------- 成本分析 ---------------- */
export function CostAnalyticsTab() {
  const [days, setDays] = useState(30)
  const { data, loading, error } = useAnalytics('cost', days)
  if (loading) return <Spinner />
  if (error) return <ErrorMsg msg={error} />
  const ov = data?.overview || {}
  return (
    <div>
      <DaysSwitch days={days} setDays={setDays} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 12, marginBottom: 24 }}>
        <StatCard label={`近${days}天总成本`} value={`¥${ov.total_cost ?? 0}`} color={C_RED} />
        <StatCard label="单条消息成本" value={`¥${ov.cost_per_message ?? 0}`} color={C_ORANGE}
          sub={`共 ${ov.messages ?? 0} 条消息`} />
      </div>
      <Card style={{ padding: '20px 24px' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 12px', color: 'var(--text-primary)' }}>每模型成本（近{days}天）</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
              {['模型', '调用次数', '输入 Token', '输出 Token', '成本(¥)'].map((h) => (
                <th key={h} style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(data?.models || []).map((m: any) => (
              <tr key={m.model} style={{ color: 'var(--text-primary)' }}>
                <td style={{ padding: '8px 8px', borderBottom: '1px solid var(--border-light)', fontFamily: 'monospace', fontSize: 11 }}>{m.model}</td>
                <td style={{ padding: '8px 8px', borderBottom: '1px solid var(--border-light)' }}>{m.calls}</td>
                <td style={{ padding: '8px 8px', borderBottom: '1px solid var(--border-light)' }}>{m.prompt_tokens.toLocaleString()}</td>
                <td style={{ padding: '8px 8px', borderBottom: '1px solid var(--border-light)' }}>{m.completion_tokens.toLocaleString()}</td>
                <td style={{ padding: '8px 8px', borderBottom: '1px solid var(--border-light)', fontWeight: 600 }}>{m.cost}</td>
              </tr>
            ))}
            {(data?.models || []).length === 0 && (
              <tr><td colSpan={5} style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)' }}>暂无用量数据</td></tr>
            )}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
