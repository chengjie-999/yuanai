import { useState, useEffect } from 'react'
import { API_BASE, headers, safeJson } from '../api'
import { SUB_AGENTS } from '../config/agents'
import { ErrorBoundary } from './ErrorBoundary'

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

  // 后端已按用户过滤（旧模式 agent_id==user_id + 设备一对一绑定），前端不再
  // 用 agent_id==userId 二次过滤——设备模式 agent_id 是设备号，曾把在线 Agent
  // 滤成空导致页面显示离线/待连接。取法同 AgentStatus：优先匹配，否则取第一个。
  const matched = agents.find((a: any) => String(a.agent_id) === String(userId))
  const myAgents = userId ? (matched ? [matched] : agents.slice(0, 1)) : agents.slice(0, 1)
  const mainOnline = myAgents.length > 0 && myAgents[0].online
  const mainAgent = myAgents[0]

  return (
    <ErrorBoundary>
    <div style={{ background: 'var(--bg-secondary)', padding: '40px', display: 'flex', justifyContent: 'center' }}>
      <div style={{ maxWidth: 560, width: '100%', display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* 运行状态 */}
        <div style={{ background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{
              width: 12, height: 12, borderRadius: '50%',
              background: mainOnline ? 'var(--success)' : 'var(--text-muted)',
              display: 'inline-block',
              boxShadow: mainOnline ? '0 0 8px rgba(76,175,80,0.4)' : undefined,
            }} />
            <span style={{ fontWeight: 600, fontSize: 16, color: mainOnline ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
              {mainOnline ? '本地Agent 运行中' : '本地Agent 离线'}
            </span>
            <div style={{ flex: 1 }} />
            <button onClick={load} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--accent)' }}>刷新</button>
          </div>
          {mainOnline && mainAgent && (
            <div style={{ marginTop: 12, fontSize: 13, color: 'var(--text-secondary)', display: 'flex', gap: 16 }}>
              <span>{mainAgent.agent_name}</span>
              <span style={{ color: 'var(--text-muted)' }}>|</span>
              <span style={{ fontFamily: 'monospace' }}>ID: {mainAgent.agent_id}</span>
              <span style={{ color: 'var(--text-muted)' }}>|</span>
              <span>心跳: {mainAgent.last_heartbeat}</span>
            </div>
          )}
          {!mainOnline && (
            <div style={{ marginTop: 12, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
              <p style={{ margin: 0 }}>请在本机启动 小元AI Agent 客户端，启动后将自动连接云端。</p>
              <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>如未安装，请到「设置页 → 本地 Agent 下载」自取安装包与安装码。</p>
            </div>
          )}
        </div>

        {/* 能力矩阵 */}
        <div style={{ background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' }}>
          <div style={{ padding: '14px 24px', borderBottom: '1px solid var(--border-light)', fontWeight: 600, fontSize: 14, color: 'var(--text-primary)', background: 'var(--bg-secondary)' }}>
            能力矩阵
          </div>
          {SUB_AGENTS.map((sa) => (
            <div key={sa.key} style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '14px 24px',
              borderBottom: '1px solid var(--border-light)',
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%', background: mainOnline ? sa.color : 'var(--text-muted)',
                display: 'inline-block', flexShrink: 0,
              }} />
              <div>
                <div style={{ fontWeight: 600, fontSize: 13, color: sa.color }}>{sa.label}</div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 1 }}>{sa.desc}</div>
              </div>
              <div style={{ flex: 1 }} />
              <span style={{ fontSize: 11, color: mainOnline ? 'var(--success)' : 'var(--text-secondary)' }}>
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
            <div key={i} style={{ background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', padding: '16px 24px' }}>
              <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)', marginBottom: 8 }}>活动记录</div>
              <div style={{ maxHeight: 200, overflow: 'auto' }}>
                {acts.map((act: any, j: number) => (
                  <div key={j} style={{
                    padding: '6px 0', borderBottom: j < acts.length - 1 ? '1px solid var(--border-light)' : 'none',
                    display: 'flex', gap: 8, alignItems: 'flex-start',
                  }}>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', minWidth: 48, flexShrink: 0 }}>{act.time}</span>
                    <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>{act.message}</span>
                    {act.detail && <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{act.detail}</span>}
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
    </ErrorBoundary>
  )
}
