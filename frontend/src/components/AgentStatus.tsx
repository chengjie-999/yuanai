import { useState, useEffect } from 'react'
import { API_BASE, getToken } from '../api'
import { MonitorIcon, MonitorOffIcon } from './icons'

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
  const agent = myAgents[0]
  const capLabels: Record<string, string> = {
    analysis: '分析工具', collection: '采集工具', automation: '自动化', claude: 'Claude Code',
  }

  // 纯图标指示灯：悬浮提示显示状态详情（文字移到 yuan-tip 气泡）
  const tip = error || !online
    ? '本地 Agent 离线'
    : '本地 Agent 在线' + (agent?.capabilities?.length
        ? ' · ' + agent.capabilities.map((c: string) => capLabels[c] || c).join(' / ')
        : '')

  return (
    <span className="yuan-tip yuan-tip-down" data-tip={tip} aria-label={tip}
      style={{
        display: 'inline-flex', alignItems: 'center', padding: 4,
        color: online ? 'var(--success)' : 'var(--text-muted)', cursor: 'default',
      }}>
      {online ? <MonitorIcon size={18} /> : <MonitorOffIcon size={18} />}
    </span>
  )
}
