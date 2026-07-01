import { useState, useEffect } from 'react'
import { Spinner, ErrorMsg, Card, CardHeader, headers, API_BASE } from './shared'

export default function DashboardTab({ isAdmin }: { isAdmin: boolean }) {
  const [data, setData] = useState<any>(null)
  const [agents, setAgents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = () => {
    fetch(`${API_BASE}/admin/dashboard`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then((d) => { setData(d); setError('') })
      .catch((e) => setError(`仪表盘加载失败: ${e.message}`))
    fetch(`${API_BASE}/admin/agent-status`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((d) => { if (Array.isArray(d)) setAgents(d) })
      .catch(() => {})
    setLoading(false)
  }

  useEffect(() => { load(); const i = setInterval(load, 15000); return () => clearInterval(i) }, [])

  const onlineCount = agents.filter((a: any) => a.online).length
  const allCards = [
    { label: '用户数', value: data?.users ?? '-', color: '#42a5f5', adminOnly: true },
    { label: '会话数', value: data?.sessions ?? '-', color: '#66bb6a', adminOnly: true },
    { label: '消息数', value: data?.messages ?? '-', color: '#ffa726', adminOnly: true },
    { label: '在线 Agent', value: onlineCount, color: '#26c6da', adminOnly: false },
    { label: '今日消息', value: data?.today_messages ?? '-', color: '#ef5350', adminOnly: false },
    { label: '今日活跃', value: data?.today_users ?? '-', color: '#ab47bc', adminOnly: false },
    { label: '均消息/会话', value: data?.avg_messages ?? '-', color: '#26a69a', adminOnly: true },
    { label: '数据集', value: data?.datasets ?? '-', color: '#8d6e63', adminOnly: false },
  ]
  const cards = isAdmin ? allCards : allCards.filter((c) => !c.adminOnly)

  return (
    <div>
      {error && <ErrorMsg msg={error} onRetry={load} />}
      {loading && <Spinner />}
      {!loading && <>
      <div className="card-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 12, marginBottom: 24 }}>
        {cards.map((c) => (
          <div key={c.label} className="stat-card" style={{ background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', padding: '14px 12px', textAlign: 'center', transition: 'box-shadow 0.2s' }}
            onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 2px 12px var(--shadow-sm)')}
            onMouseLeave={(e) => (e.currentTarget.style.boxShadow = '')}>
            <div style={{ fontSize: 24, fontWeight: 700, color: c.color, lineHeight: 1.3 }}>{c.value}</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{c.label}</div>
          </div>
        ))}
      </div>
      {isAdmin && data?.daily_messages?.length > 0 && (
        <Card style={{ marginBottom: 24, padding: '20px 24px' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px', color: 'var(--text-primary)' }}>近30天消息量</h3>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 100, padding: '0 4px' }}>
            {data.daily_messages.map((d: any, i: number) => {
              const max = Math.max(...data.daily_messages.map((x: any) => x.count), 1)
              const h = Math.max((d.count / max) * 80, d.count > 0 ? 4 : 0)
              return (
                <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '100%' }}>
                  <div style={{ width: '100%', maxWidth: 24, height: h, background: d.count > 0 ? 'linear-gradient(180deg, #42a5f5, #1e88e5)' : 'var(--bg-tertiary)', borderRadius: '3px 3px 0 0', transition: 'opacity 0.15s', cursor: 'default', opacity: 0.75 }}
                    title={`${d.date}: ${d.count} 条`}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.75')} />
                </div>
              )
            })}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 10, color: 'var(--text-muted)' }}>
            <span>{data.daily_messages[0]?.date}</span>
            <span>{data.daily_messages[data.daily_messages.length - 1]?.date}</span>
          </div>
        </Card>
      )}
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
