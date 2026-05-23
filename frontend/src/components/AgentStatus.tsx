import { useState, useEffect } from 'react'
import { API_BASE, getToken } from '../api'

interface AgentInfo {
  agent_id: string
  agent_name: string
  capabilities: string[]
  online: boolean
  last_heartbeat: string
}

export default function AgentStatus() {
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
          } catch { /* ignore parse errors */ }
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

  if (error || agents.length === 0) {
    return (
      <span style={{ fontSize: 12, color: '#999', display: 'flex', alignItems: 'center', gap: 4 }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%', background: '#ccc',
          display: 'inline-block',
        }} />
        本地 Agent 离线
      </span>
    )
  }

  const agent = agents[0]
  const capLabels: Record<string, string> = {
    analysis: '分析', collection: '采集', automation: '自动化',
  }

  return (
    <span style={{ fontSize: 12, color: '#333', display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        width: 8, height: 8, borderRadius: '50%',
        background: agent.online ? '#4caf50' : '#ff9800',
        display: 'inline-block',
        boxShadow: agent.online ? '0 0 6px rgba(76,175,80,0.5)' : undefined,
      }} />
      {agent.agent_name}
      <span style={{ color: '#999' }}>
        {agent.capabilities.map((c) => capLabels[c] || c).join('·')}
      </span>
    </span>
  )
}
