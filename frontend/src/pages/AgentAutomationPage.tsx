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
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#fafafa' }}>
      <div style={{
        padding: '10px 20px', background: '#fff', borderBottom: '1px solid #e8e8ec',
        display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0,
      }}>
        <Link to="/" style={{
          fontSize: 12, color: '#999', textDecoration: 'none',
          padding: '4px 10px', borderRadius: 6, border: '1px solid #e0e0e0',
        }}>← 返回对话</Link>
        <span style={{ fontSize: 18, lineHeight: 1 }}>🤖</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: agent.color, display: 'flex', alignItems: 'center', gap: 8 }}>
            自动化 Agent
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: agentOnline ? '#4caf50' : '#ccc',
              display: 'inline-block',
            }} />
            <span style={{ fontSize: 11, color: agentOnline ? '#4caf50' : '#999', fontWeight: 400 }}>
              {agentOnline ? '在线' : '离线'}
            </span>
          </div>
          <div style={{ fontSize: 11, color: '#999' }}>浏览器控制、截图监控、题目审核</div>
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'auto', maxWidth: 900, margin: '0 auto', width: '100%', padding: 20, boxSizing: 'border-box' }}>
        <AutomationPanel agentOnline={agentOnline} />
      </div>
    </div>
  )
}
