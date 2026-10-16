import { useState, useEffect } from 'react'
import { API_BASE, headers, safeJson } from '../api'
import { SUB_AGENTS } from '../config/agents'
import { ErrorBoundary } from './ErrorBoundary'
import { XIcon } from './icons'

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

        {/* 模型配置 */}
        <ModelsCard />

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
              <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>如未安装，请联系管理员获取安装包。</p>
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

function ModelsCard() {
  const [models, setModels] = useState<Record<string, any>>({})
  const [showModal, setShowModal] = useState(false)
  const [newId, setNewId] = useState('')
  const [newProvider, setNewProvider] = useState('Custom')
  const [newKey, setNewKey] = useState('')

  const loadModels = () => {
    fetch(`${API_BASE}/admin/models`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((data) => { if (data && typeof data === 'object' && !Array.isArray(data)) setModels(data) })
      .catch(() => {})
  }
  useEffect(() => { loadModels() }, [])

  const handleAdd = async () => {
    if (!newId.trim()) return
    // label 用模型 ID 本身（显示名无意义）
    await fetch(`${API_BASE}/admin/models`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ model_id: newId.trim(), label: newId.trim(), provider: newProvider.trim() || 'Custom' }),
    })
    if (newKey.trim()) {
      await fetch(`${API_BASE}/admin/apikeys`, {
        method: 'POST', headers: headers(),
        body: JSON.stringify({ provider: newProvider.trim() || 'Custom', key: newKey.trim() }),
      })
    }
    setShowModal(false); setNewId(''); setNewLabel(''); setNewProvider('Custom'); setNewKey('')
    loadModels()
  }

  const handleDelete = async (id: string) => {
    await fetch(`${API_BASE}/admin/models`, {
      method: 'DELETE', headers: headers(),
      body: JSON.stringify({ model_id: id }),
    })
    loadModels()
  }

  return (
    <div style={{ background: "var(--bg-primary)", borderRadius: 12, border: "1px solid var(--border)", overflow: "hidden" }}>
      <div style={{ padding: "14px 24px", borderBottom: "1px solid var(--border-light)", fontWeight: 600, fontSize: 14, color: "var(--text-primary)", background: "var(--bg-secondary)", display: 'flex', alignItems: 'center' }}>
        模型配置
        <div style={{ flex: 1 }} />
        <button onClick={() => setShowModal(true)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: 'var(--accent)' }}>+ 添加</button>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ background: "var(--bg-tertiary)" }}>
            <th style={{ padding: "10px 14px", textAlign: "left", fontSize: 12, color: "var(--text-secondary)" }}>模型 ID</th>
            <th style={{ padding: "10px 14px", textAlign: "left", fontSize: 12, color: "var(--text-secondary)" }}>供应商</th>
            <th style={{ padding: "10px 14px", textAlign: "left", fontSize: 12, color: "var(--text-secondary)", width: 40 }}></th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(models).map(([id, info]) => {
            if (!info || typeof info !== 'object') return null
            return (
            <tr key={id} style={{ borderBottom: "1px solid var(--border-light)" }}>
              <td style={{ padding: "10px 14px", fontFamily: 'monospace', fontSize: 12, color: 'var(--text-primary)' }}>{id}</td>
              <td style={{ padding: "10px 14px", color: "var(--text-secondary)", fontSize: 12 }}>{info.provider as string}</td>
              <td style={{ padding: "10px 14px" }}>
                {!info.builtin && <button onClick={() => handleDelete(id)} title="删除" aria-label="删除"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '4px', lineHeight: 1, display: 'flex' }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--danger)')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}><XIcon size={13} /></button>}
              </td>
            </tr>
          )})}
        </tbody>
      </table>
      {showModal && (
        <div onClick={() => setShowModal(false)} style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: 'var(--bg-primary)', borderRadius: 12, padding: 24, minWidth: 360, boxShadow: '0 8px 40px var(--shadow-md)' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>添加模型</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <input value={newId} onChange={(e) => setNewId(e.target.value)} placeholder="模型 ID (如 doubao-seed-2-1-lite-260915)" style={{ ...inputStyle, fontFamily: 'monospace' }} />
              <input value={newProvider} onChange={(e) => setNewProvider(e.target.value)} placeholder="供应商 (如 Doubao/DeepSeek)" style={inputStyle} />
              <input value={newKey} onChange={(e) => setNewKey(e.target.value)} placeholder="API Key (可选)" style={inputStyle} />
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowModal(false)} style={{ padding: '6px 16px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-primary)', cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)' }}>取消</button>
              <button onClick={handleAdd} style={{ padding: '6px 16px', borderRadius: 6, border: 'none', background: 'var(--accent)', color: '#fff', cursor: 'pointer', fontSize: 13 }}>确认添加</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const inputStyle: React.CSSProperties = { padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)' }
