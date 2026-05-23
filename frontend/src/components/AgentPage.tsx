import { useState, useEffect } from 'react'
import { API_BASE, getToken } from '../api'

function headers() {
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  const t = getToken()
  if (t) h['Authorization'] = `Bearer ${t}`
  return h
}

async function safeJson(res: Response): Promise<any> {
  const text = await res.text()
  try { return JSON.parse(text) }
  catch { return null }
}

const SUB_AGENTS = [
  { key: 'orchestrator', label: '统筹 Agent', desc: '意图识别与任务分发', color: '#1976d2' },
  { key: 'analysis', label: '数据分析 Agent', desc: '数据集管理、统计分析、图表生成', color: '#7b1fa2' },
  { key: 'collection', label: '数据采集 Agent', desc: '网页爬取、数据抓取、内容提取', color: '#00695c' },
  { key: 'automation', label: '自动化 Agent', desc: '浏览器控制、题目审核、截图监控', color: '#e65100' },
]

export default function AgentPage({ userId }: { userId?: number }) {
  const [agents, setAgents] = useState<any[]>([])

  const load = async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/agent-status`, { headers: headers() })
      const data = await safeJson(res)
      if (Array.isArray(data)) setAgents(data)
    } catch {}
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [])

  const myAgents = agents.filter((a: any) => !userId || String(a.agent_id) === String(userId))
  const mainOnline = myAgents.length > 0 && myAgents[0].online
  const mainAgent = myAgents[0]

  return (
    <div style={{ height: '100%', overflow: 'auto', background: '#f8f9fb', padding: '40px', display: 'flex', justifyContent: 'center' }}>
      <div style={{ maxWidth: 560, width: '100%', display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* 运行状态 */}
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #eee', padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{
              width: 12, height: 12, borderRadius: '50%',
              background: mainOnline ? '#4caf50' : '#ccc',
              display: 'inline-block',
              boxShadow: mainOnline ? '0 0 8px rgba(76,175,80,0.4)' : undefined,
            }} />
            <span style={{ fontWeight: 600, fontSize: 16, color: mainOnline ? '#333' : '#999' }}>
              {mainOnline ? 'Agent 运行中' : 'Agent 离线'}
            </span>
            <div style={{ flex: 1 }} />
            <button onClick={load} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: '#1976d2' }}>刷新</button>
          </div>
          {mainOnline && mainAgent && (
            <div style={{ marginTop: 12, fontSize: 13, color: '#666', display: 'flex', gap: 16 }}>
              <span>{mainAgent.agent_name}</span>
              <span style={{ color: '#bbb' }}>|</span>
              <span style={{ fontFamily: 'monospace' }}>ID: {mainAgent.agent_id}</span>
              <span style={{ color: '#bbb' }}>|</span>
              <span>心跳: {mainAgent.last_heartbeat}</span>
            </div>
          )}
          {!mainOnline && (
            <code style={{ display: 'block', marginTop: 12, background: '#f5f5f8', padding: '8px 12px', borderRadius: 6, fontSize: 12, color: '#666' }}>
              python agent/main.py --agent-id {userId || 'ID'}
            </code>
          )}
        </div>

        {/* 子 Agent 团队 */}
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #eee', overflow: 'hidden' }}>
          <div style={{ padding: '14px 24px', borderBottom: '1px solid #f0f0f0', fontWeight: 600, fontSize: 14, color: '#333', background: '#fafafa' }}>
            子 Agent 团队
          </div>
          {SUB_AGENTS.map((sa) => (
            <div key={sa.key} style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '14px 24px',
              borderBottom: '1px solid #f5f5f5',
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%', background: mainOnline ? sa.color : '#ddd',
                display: 'inline-block', flexShrink: 0,
              }} />
              <div>
                <div style={{ fontWeight: 600, fontSize: 13, color: sa.color }}>{sa.label}</div>
                <div style={{ fontSize: 12, color: '#999', marginTop: 1 }}>{sa.desc}</div>
              </div>
              <div style={{ flex: 1 }} />
              <span style={{ fontSize: 11, color: mainOnline ? '#4caf50' : '#999' }}>
                {mainOnline ? '就绪' : '待连接'}
              </span>
            </div>
          ))}
        </div>

        {/* 活动记录 */}
        {myAgents.map((a, i) => {
          const acts = a.activities || []
          if (acts.length === 0) return null
          return (
            <div key={i} style={{ background: '#fff', borderRadius: 12, border: '1px solid #eee', padding: '16px 24px' }}>
              <div style={{ fontWeight: 600, fontSize: 14, color: '#333', marginBottom: 8 }}>活动记录</div>
              <div style={{ maxHeight: 200, overflow: 'auto' }}>
                {acts.map((act: any, j: number) => (
                  <div key={j} style={{
                    padding: '6px 0', borderBottom: j < acts.length - 1 ? '1px solid #f5f5f5' : 'none',
                    display: 'flex', gap: 8, alignItems: 'flex-start',
                  }}>
                    <span style={{ fontSize: 11, color: '#bbb', minWidth: 48, flexShrink: 0 }}>{act.time}</span>
                    <span style={{ fontSize: 13, color: '#333' }}>{act.message}</span>
                    {act.detail && <span style={{ fontSize: 11, color: '#999' }}>{act.detail}</span>}
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
