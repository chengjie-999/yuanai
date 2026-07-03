import { useState, useEffect } from 'react'
import { Spinner, Empty, ErrorMsg, Card, CardHeader, headers, API_BASE } from './shared'
import { SUB_AGENTS } from '../../config/agents'

export default function AgentsTab() {
  const [agents, setAgents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = () => {
    fetch(`${API_BASE}/admin/agent-status`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((d) => { if (Array.isArray(d)) { setAgents(d); setError('') } })
      .catch(() => setError('加载 Agent 状态失败'))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load(); const i = setInterval(load, 10000); return () => clearInterval(i) }, [])

  const online = agents.filter((a) => a.online)
  const offline = agents.filter((a) => !a.online)
  const allActivities = agents.flatMap((a) => (a.activities || []).map((act: any) => ({ ...act, agent: a.agent_name, agentId: a.agent_id })))
    .sort((a: any, b: any) => (b.time || '').localeCompare(a.time || '')).slice(0, 20)

  if (loading) return <Spinner />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {error && <ErrorMsg msg={error} onRetry={load} />}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        {[
          { label: 'Agent 总数', value: agents.length, color: 'var(--accent)' },
          { label: '在线', value: online.length, color: 'var(--success)' },
          { label: '离线', value: offline.length, color: 'var(--text-muted)' },
          { label: '子 Agent 类型', value: SUB_AGENTS.length, color: '#ff9800' },
        ].map((c) => (
          <div key={c.label} style={{ background: 'var(--bg-primary)', borderRadius: 10, border: '1px solid var(--border)', padding: '14px 16px', textAlign: 'center' }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: c.color }}>{c.value}</div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>{c.label}</div>
          </div>
        ))}
      </div>

      <Card>
        <CardHeader title={`Agent 列表 (${agents.length})`} action={<button onClick={load} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: 'var(--accent)' }}>刷新</button>} />
        {agents.length === 0 ? <Empty msg="暂无 Agent 连接" /> : (
          agents.map((a) => (
            <div key={a.agent_id} style={{ padding: '14px 20px', borderBottom: '1px solid var(--border-light)', display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: a.online ? 'var(--success)' : 'var(--text-muted)', flexShrink: 0, boxShadow: a.online ? '0 0 8px rgba(76,175,80,0.4)' : undefined }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: a.online ? 'var(--text-primary)' : 'var(--text-muted)' }}>{a.agent_name}</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>ID: {a.agent_id}{a.last_heartbeat && <span style={{ marginLeft: 12 }}>心跳: {a.last_heartbeat}</span>}</div>
              </div>
              <span style={{ fontSize: 12, fontWeight: 600, color: a.online ? 'var(--success)' : 'var(--text-muted)' }}>{a.online ? '在线' : '离线'}</span>
            </div>
          ))
        )}
      </Card>

      <Card>
        <CardHeader title="子 Agent 团队" />
        {SUB_AGENTS.map((sa) => (
          <div key={sa.key} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 20px', borderBottom: '1px solid var(--border-light)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: online.length > 0 ? sa.color : 'var(--text-muted)', flexShrink: 0 }} />
            <div><div style={{ fontWeight: 600, fontSize: 13, color: sa.color }}>{sa.label}</div><div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 1 }}>{sa.desc}</div></div>
            <div style={{ flex: 1 }} />
            <span style={{ fontSize: 11, color: online.length > 0 ? 'var(--success)' : 'var(--text-muted)' }}>{online.length > 0 ? '就绪' : '待连接'}</span>
          </div>
        ))}
      </Card>

      {allActivities.length > 0 && (
        <Card>
          <CardHeader title="全局活动记录" />
          <div style={{ maxHeight: 300, overflow: 'auto' }}>
            {allActivities.map((act: any, j: number) => (
              <div key={j} style={{ padding: '8px 20px', borderBottom: j < allActivities.length - 1 ? '1px solid var(--border-light)' : 'none', display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', minWidth: 52, flexShrink: 0 }}>{act.time}</span>
                <span style={{ fontSize: 11, color: 'var(--accent)', minWidth: 80, flexShrink: 0 }}>[{act.agent}]</span>
                <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>{act.message}</span>
                {act.detail && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{act.detail}</span>}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
