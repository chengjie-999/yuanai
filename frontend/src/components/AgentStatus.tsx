import { useState, useEffect } from 'react'
import { API_BASE, getToken } from '../api'

interface AgentInfo {
  agent_id: string
  agent_name: string
  capabilities: string[]
  online: boolean
  last_heartbeat: string
}

export default function AgentStatus({ userId }: { userId?: number }) {
  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [error, setError] = useState(false)

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/admin/agent-status`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        })
        if (res.ok) {
          const text = await res.text()
          try {
            const data = JSON.parse(text)
            if (Array.isArray(data)) setAgents(data)
          } catch {}
          setError(false)
        }
      } catch {
        setError(true)
      }
    }
    fetchStatus()
    const interval = setInterval(fetchStatus, 10000)
    return () => clearInterval(interval)
  }, [])

  // 后端已按用户过滤（旧模式直连或绑定设备）；这里优先匹配 user_id，否则取第一个
  const matched = agents.find((a) => String(a.agent_id) === String(userId))
  const myAgents = userId ? (matched ? [matched] : agents.slice(0, 1)) : agents.slice(0, 1)
  const online = myAgents.length > 0 && myAgents[0].online

  if (error || !online) {
    return (
      <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%', background: 'var(--text-muted)',
          display: 'inline-block',
        }} />
        本地Agent 离线
      </span>
    )
  }

  const agent = myAgents[0]
  const capLabels: Record<string, string> = {
    analysis: '分析', collection: '采集', automation: '自动化', claude: 'Claude Code',
  }

  return (
    <span style={{ fontSize: 12, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        width: 8, height: 8, borderRadius: '50%',
        background: 'var(--success)',
        display: 'inline-block',
        boxShadow: '0 0 6px rgba(76,175,80,0.5)',
      }} />
      {agent.agent_name}
      <span style={{ color: 'var(--text-muted)' }}>
        {agent.capabilities.map((c: string) => capLabels[c] || c).join('·')}
      </span>
    </span>
  )
}
