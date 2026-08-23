import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import AutomationPanel from '../components/chat/panels/AutomationPanel'
import { AGENT_CONFIG } from '../config/agents'
import { API_BASE } from '../api'

export default function AgentAutomationPage() {
  const agent = AGENT_CONFIG.automation
  const [agentOnline, setAgentOnline] = useState(false)

  useEffect(() => {
    const poll = () => {
      const token = localStorage.getItem('token')
      if (!token) return
      fetch(`${API_BASE}/admin/agent-status`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => r.json())
        .then((data) => {
          if (Array.isArray(data)) {
            const online = data.some((a: any) =>
              a.capabilities?.includes('automation') && a.online
            )
            setAgentOnline(online)
          }
        })
        .catch(() => {})
    }
    poll()
    const i = setInterval(poll, 15000)
    return () => clearInterval(i)
  }, [])

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--bg-secondary)' }}>
      <div style={{
        padding: '8px 12px', background: 'var(--header-bg)', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
      }}>
        <Link to="/chat" style={{
          fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none',
          padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border)',
          flexShrink: 0,
        }}>← 返回</Link>
        <span style={{ fontSize: 18, lineHeight: 1 }}>🤖</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: agent.color, display: 'flex', alignItems: 'center', gap: 8 }}>
            自动化 Agent
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: agentOnline ? 'var(--success)' : 'var(--text-muted)',
              display: 'inline-block',
            }} />
            <span style={{ fontSize: 11, color: agentOnline ? 'var(--success)' : 'var(--text-secondary)', fontWeight: 400 }}>
              {agentOnline ? '在线' : '离线'}
            </span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>浏览器控制、截图监控、题目审核</div>
        </div>
      </div>
      <div className="agent-page-body" style={{ flex: 1, overflow: 'auto', maxWidth: 900, margin: '0 auto', width: '100%', boxSizing: 'border-box' }}>
        <AutomationPanel agentOnline={agentOnline} />
      </div>
    </div>
  )
}
