import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import AutomationPanel from '../components/chat/panels/AutomationPanel'
import { AGENT_CONFIG } from '../config/agents'
import { API_BASE, authHeaders, getToken } from '../api'
import { ArrowLeftIcon, BotIcon } from '../components/icons'

export default function AgentAutomationPage({ onClose, hideBack }: { onClose?: () => void; hideBack?: boolean } = {}) {
  const agent = AGENT_CONFIG.automation
  const [agentOnline, setAgentOnline] = useState(false)

  useEffect(() => {
    const poll = () => {
      if (!getToken()) return
      fetch(`${API_BASE}/admin/agent-status`, {
        headers: authHeaders(),
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
        {hideBack ? null : onClose ? (
        <button onClick={onClose} style={{
          fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none',
          padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border)',
          flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4, lineHeight: 1,
          background: 'transparent', cursor: 'pointer',
        }}><ArrowLeftIcon size={12} /> 返回对话</button>
      ) : (
        <Link to="/chat" style={{
          fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none',
          padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border)',
          flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4, lineHeight: 1,
        }}><ArrowLeftIcon size={12} /> 返回</Link>
      )}
        <span style={{ lineHeight: 1, color: agent.color, display: 'flex' }}><BotIcon size={18} /></span>
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
