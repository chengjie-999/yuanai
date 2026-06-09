import { useState, useEffect } from 'react'
import { API_BASE } from '../../../api'

export default function AutomationPanel({ agentOnline }: { agentOnline: boolean }) {
  const [screenshot] = useState<string | null>(null)
  const [status, setStatus] = useState<string>('')
  const [activities, setActivities] = useState<any[]>([])

  useEffect(() => {
    if (!agentOnline) return
    const poll = () => {
      const token = localStorage.getItem('token')
      if (!token) return
      fetch(`${API_BASE}/admin/agent-status`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => r.json())
        .then((data) => {
          if (Array.isArray(data)) {
            const autoAgent = data.find((a: any) =>
              a.capabilities?.includes('automation') && a.online
            )
            if (autoAgent) {
              setStatus(autoAgent.online ? '运行中' : '')
              setActivities(autoAgent.activities || [])
            }
          }
        })
        .catch(() => {})
    }
    poll()
    const i = setInterval(poll, 8000)
    return () => clearInterval(i)
  }, [agentOnline])

  if (!agentOnline) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8, color: '#bbb', padding: 40 }}>
        <div style={{ fontSize: 40, opacity: 0.3 }}>📡</div>
        <div style={{ fontSize: 13, color: '#999' }}>自动化 Agent 离线</div>
        <div style={{ fontSize: 12, color: '#ccc', textAlign: 'center' }}>请启动本地 Agent 后重试</div>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%', background: '#4caf50',
            display: 'inline-block', boxShadow: '0 0 6px rgba(76,175,80,0.5)',
          }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: '#333' }}>浏览器</span>
          <span style={{ fontSize: 12, color: '#4caf50' }}>{status || '运行中'}</span>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        {screenshot ? (
          <div style={{ padding: 8 }}>
            <img src={screenshot} style={{ width: '100%', borderRadius: 8, border: '1px solid #eee' }} alt="截屏" />
          </div>
        ) : (
          <div style={{ textAlign: 'center', color: '#ccc', padding: 30, fontSize: 13 }}>
            <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.3 }}>🖥️</div>
            浏览器就绪，等待任务...
          </div>
        )}

        {activities.length > 0 && (
          <div style={{ padding: '0 14px' }}>
            <div style={{ fontSize: 11, color: '#bbb', marginBottom: 6, fontWeight: 600 }}>活动记录</div>
            {activities.slice(0, 10).map((act: any, j: number) => (
              <div key={j} style={{
                padding: '4px 0', borderBottom: '1px solid #f5f5f5',
                display: 'flex', gap: 6, fontSize: 11,
              }}>
                <span style={{ color: '#bbb', flexShrink: 0 }}>{act.time}</span>
                <span style={{ color: '#666' }}>{act.message}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
