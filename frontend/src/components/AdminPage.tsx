import { Component, useState, useEffect } from 'react'
import { API_BASE, getToken, fetchWebsites, addWebsite, deleteWebsite, freezeUser } from '../api'

const TABS = [
  { key: 'dashboard', label: '仪表盘' },
  { key: 'users', label: '用户管理' },
  { key: 'websites', label: '网站管理' },
  { key: 'agents', label: 'Agent 状态' },
  { key: 'models', label: '模型配置' },
]

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

class ErrorBoundary extends Component<{ children: React.ReactNode }, { hasError: boolean; error: string }> {
  state = { hasError: false, error: '' }
  static getDerivedStateFromError(e: Error) { return { hasError: true, error: e.message } }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, textAlign: 'center', color: '#e53935' }}>
          <h3>页面加载异常</h3>
          <p style={{ fontSize: 13, color: '#999' }}>{this.state.error}</p>
          <button onClick={() => this.setState({ hasError: false })} style={{ marginTop: 12, padding: '6px 16px', cursor: 'pointer' }}>重试</button>
        </div>
      )
    }
    return this.props.children
  }
}

// ==================== 仪表盘 ====================

function DashboardTab() {
  const [data, setData] = useState<any>(null)
  const [agents, setAgents] = useState<any[]>([])

  useEffect(() => {
    fetch(`${API_BASE}/admin/dashboard`, { headers: headers() })
      .then(safeJson).then((d) => { if (d && typeof d === 'object') setData(d) }).catch(() => {})
    fetch(`${API_BASE}/admin/agent-status`, { headers: headers() })
      .then(safeJson).then((a) => { if (Array.isArray(a)) setAgents(a) }).catch(() => {})
  }, [])

  const agentList = Array.isArray(agents) ? agents : []
  const onlineCount = agentList.filter((a: any) => a.online).length

  const cards = [
    { label: '用户数', value: data?.users ?? '-', color: '#42a5f5' },
    { label: '会话数', value: data?.sessions ?? '-', color: '#66bb6a' },
    { label: '消息数', value: data?.messages ?? '-', color: '#ffa726' },
    { label: '在线 Agent', value: onlineCount, color: '#4caf50' },
  ]

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px,1fr))', gap: 12, marginBottom: 24 }}>
        {cards.map((c) => (
          <div key={c.label} style={{ background: '#fff', borderRadius: 10, border: '1px solid #eee', padding: '14px 16px', textAlign: 'center' }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: c.color }}>{c.value}</div>
            <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>{c.label}</div>
          </div>
        ))}
      </div>

      {data?.daily_messages?.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: '#333' }}>近30天消息量</h3>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 80, background: '#fff', borderRadius: 8, padding: 12 }}>
            {data.daily_messages.map((d: any, i: number) => {
              const max = Math.max(...data.daily_messages.map((x: any) => x.count), 1)
              const h = (d.count / max) * 60
              return (
                <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end' }}>
                  <div style={{ width: '100%', maxWidth: 20, height: h, background: '#42a5f5', borderRadius: '2px 2px 0 0', opacity: 0.7 }}
                    title={`${d.date}: ${d.count}`} />
                </div>
              )
            })}
          </div>
        </div>
      )}

      {agents.length > 0 && (
        <div>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: '#333' }}>Agent 列表</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, background: '#fff', borderRadius: 8, overflow: 'hidden' }}>
            <thead>
              <tr style={{ background: '#f5f5f8' }}>
                {['名称', '状态', '能力', '最后心跳'].map((h) => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {agents.map((a: any, i: number) => (
                <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 600 }}>{a.agent_name}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{
                      display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                      background: a.online ? '#4caf50' : '#ccc', marginRight: 6,
                    }} />
                    {a.online ? '在线' : '离线'}
                  </td>
                  <td style={{ padding: '10px 14px', color: '#666', fontSize: 12 }}>
                    {a.capabilities?.join(', ') || '-'}
                  </td>
                  <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{a.last_heartbeat || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ==================== 用户管理 ====================

function UsersTab() {
  const [users, setUsers] = useState<any[]>([])
  const [, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState('user')

  const fetchUsers = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/admin/users`, { headers: headers() })
      if (!res.ok) { setError('获取失败'); setLoading(false); return }
      setUsers(await res.json())
    } catch { setError('网络错误') }
    setLoading(false)
  }

  useEffect(() => { fetchUsers() }, [])

  const handleFreeze = async (userId: number, days: number) => {
    setError('')
    const data = await freezeUser(userId, days)
    if (data.detail) { setError(data.detail); return }
    fetchUsers()
  }

  const handleDeleteUser = async (userId: number, username: string) => {
    if (!confirm(`确定删除用户 "${username}"？此操作不可恢复。`)) return
    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}`, { method: 'DELETE', headers: headers() })
      const data = await res.json()
      if (!res.ok) { setError(data.detail || '删除失败'); return }
      fetchUsers()
    } catch { setError('删除失败') }
  }

  const handleCreateUser = async () => {
    if (!newUsername.trim() || !newPassword.trim()) { setError('请填写用户名和密码'); return }
    setError('')
    try {
      const res = await fetch(`${API_BASE}/admin/users/create`, {
        method: 'POST', headers: headers(),
        body: JSON.stringify({ username: newUsername, password: newPassword, role: newRole }),
      })
      const data = await res.json()
      if (data.error) { setError(data.error); return }
      setShowCreate(false); setNewUsername(''); setNewPassword('')
      fetchUsers()
    } catch { setError('创建失败') }
  }

  return (
    <>
      {error && <div style={{ color: '#e53935', fontSize: 13, padding: 8, background: '#fff0f0', borderRadius: 6, marginBottom: 12 }}>{error}</div>}
      <div style={{ marginBottom: 12 }}>
        {!showCreate ? (
          <button onClick={() => setShowCreate(true)} style={{
            background: '#1976d2', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 14px', cursor: 'pointer', fontSize: 13,
          }}>+ 创建用户</button>
        ) : (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} placeholder="用户名" style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ddd', fontSize: 13, outline: 'none', width: 120 }} />
            <input value={newPassword} onChange={(e) => setNewPassword(e.target.value)} type="password" placeholder="密码" style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ddd', fontSize: 13, outline: 'none', width: 120 }} />
            <select value={newRole} onChange={(e) => setNewRole(e.target.value)} style={{ padding: '6px 8px', borderRadius: 4, border: '1px solid #ddd', fontSize: 13, outline: 'none' }}>
              <option value="user">user</option>
              <option value="admin">admin</option>
            </select>
            <button onClick={handleCreateUser} style={{ background: '#1976d2', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 14px', cursor: 'pointer', fontSize: 13 }}>确定</button>
            <button onClick={() => setShowCreate(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: '#999', padding: '4px' }}>取消</button>
          </div>
        )}
      </div>
      <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #eee', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#f5f5f8' }}>
              {['ID', '用户名', '角色', '状态', '注册时间', '操作'].map((h) => (
                <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600, borderBottom: '2px solid #e0e0e0' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const isAdmin = u.role === 'admin'
              const isFrozen = u.frozen
              return (
                <tr key={u.id} style={{ borderBottom: '1px solid #f0f0f0', opacity: isFrozen ? 0.6 : 1 }}>
                  <td style={{ padding: '10px 14px', color: '#999' }}>{u.id}</td>
                  <td style={{ padding: '10px 14px', color: '#333', fontWeight: 600 }}>
                    {u.username}
                    {isAdmin && <span style={{ marginLeft: 6, fontSize: 11, color: '#1976d2', background: '#e3f2fd', padding: '1px 6px', borderRadius: 4 }}>管理员</span>}
                    {isFrozen && <span style={{ marginLeft: 6, fontSize: 11, color: '#e53935', background: '#ffebee', padding: '1px 6px', borderRadius: 4 }}>已冻结</span>}
                  </td>
                  <td style={{ padding: '10px 14px' }}>{isAdmin ? <span style={{ color: '#1976d2', fontWeight: 600 }}>admin</span> : <span style={{ color: '#666' }}>user</span>}</td>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: '#999' }}>{isFrozen ? `冻结至 ${u.frozen_until?.slice(0, 10)}` : '正常'}</td>
                  <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{u.create_time?.slice(0, 10)}</td>
                  <td style={{ padding: '10px 14px' }}>
                    {!isAdmin && (
                      <div style={{ display: 'flex', gap: 4 }}>
                        {isFrozen ? (
                          <button onClick={() => handleFreeze(u.id, 0)} style={{ fontSize: 11, padding: '4px 10px', color: '#388e3c', border: '1px solid #388e3c', background: 'none', borderRadius: 4, cursor: 'pointer' }}>解冻</button>
                        ) : (
                          <FreezeBtn userId={u.id} onFreeze={handleFreeze} />
                        )}
                        <button onClick={() => handleDeleteUser(u.id, u.username)} style={{ fontSize: 11, padding: '4px 8px', color: '#e53935', border: '1px solid #e53935', background: 'none', borderRadius: 4, cursor: 'pointer' }}>删除</button>
                      </div>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}

function FreezeBtn({ userId, onFreeze }: { userId: number; onFreeze: (id: number, days: number) => void }) {
  const [open, setOpen] = useState(false)
  const [days, setDays] = useState(7)
  if (!open) return <button onClick={() => setOpen(true)} style={{ fontSize: 11, padding: '4px 10px', color: '#e53935', border: '1px solid #e53935', background: 'none', borderRadius: 4, cursor: 'pointer' }}>冻结</button>
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
      <input type="number" min={1} max={365} value={days} onChange={(e) => setDays(Number(e.target.value))}
        style={{ width: 50, padding: '4px 6px', borderRadius: 4, border: '1px solid #ddd', fontSize: 11, outline: 'none' }} />
      <span style={{ fontSize: 11, color: '#999' }}>天</span>
      <button onClick={() => { onFreeze(userId, days); setOpen(false) }} style={{ fontSize: 11, padding: '4px 8px', color: '#fff', background: '#e53935', border: 'none', borderRadius: 4, cursor: 'pointer' }}>确定</button>
      <button onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: '#999', padding: '2px 4px' }}>✕</button>
    </div>
  )
}

// ==================== 网站管理 ====================

function WebsitesTab() {
  const [websites, setWebsites] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [newName, setNewName] = useState('')
  const [newUrl, setNewUrl] = useState('')
  const [newRemark, setNewRemark] = useState('')
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})

  const parseUrls = (w: any): string[] => {
    if (Array.isArray(w.url)) return w.url
    if (typeof w.url === 'string') {
      try { const j = JSON.parse(w.url); return Array.isArray(j) ? j : [w.url] }
      catch { return [w.url] }
    }
    return [String(w.url)]
  }

  const load = async () => {
    setLoading(true)
    const data = await fetchWebsites()
    setWebsites(data)
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const handleAdd = async () => {
    if (!newName.trim() || !newUrl.trim()) return
    const urls = newUrl.split(/[,，]/).map((u) => u.trim()).filter(Boolean)
    const r = await addWebsite(newName, JSON.stringify(urls), newRemark)
    if (r.error) { setError(r.error); return }
    setShowAdd(false); setNewName(''); setNewUrl(''); setNewRemark('')
    setError('')
    load()
  }

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`删除网站 "${name}"？`)) return
    if (await deleteWebsite(id)) load()
  }

  if (loading) return <div style={{ textAlign: 'center', color: '#999', padding: 40 }}>加载中...</div>
  return (
    <>
      {error && <div style={{ color: '#e53935', fontSize: 13, padding: 8, background: '#fff0f0', borderRadius: 6, marginBottom: 12 }}>{error}</div>}
      <div style={{ marginBottom: 12 }}>
        {!showAdd ? (
          <button onClick={() => setShowAdd(true)} style={{ background: '#1976d2', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 14px', cursor: 'pointer', fontSize: 13 }}>+ 添加网站</button>
        ) : (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="名称" style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ddd', fontSize: 13, outline: 'none', width: 120 }} />
            <input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="URL（多行用逗号分隔）" style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ddd', fontSize: 13, outline: 'none', width: 300 }} />
            <input value={newRemark} onChange={(e) => setNewRemark(e.target.value)} placeholder="备注（可选）" style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ddd', fontSize: 13, outline: 'none', width: 150 }} />
            <button onClick={handleAdd} style={{ background: '#1976d2', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 14px', cursor: 'pointer', fontSize: 13 }}>确定</button>
            <button onClick={() => setShowAdd(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: '#999', padding: '4px' }}>取消</button>
          </div>
        )}
      </div>
      <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #eee', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#f5f5f8' }}>
              {['名称', 'URL', '备注', '操作'].map((h) => (
                <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600, borderBottom: '2px solid #e0e0e0' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {websites.length === 0 && (
              <tr><td colSpan={4} style={{ padding: 30, textAlign: 'center', color: '#999' }}>暂无网站</td></tr>
            )}
            {websites.map((w) => {
              const urls = parseUrls(w)
              const isExpanded = expanded[w.id]
              return (
                <tr key={w.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 600, color: '#333' }}>{w.name}</td>
                  <td style={{ padding: '10px 14px', color: '#1976d2', fontSize: 12 }}>
                    <div>{urls[0]}</div>
                    {urls.length > 1 && (
                      <>
                        {isExpanded ? urls.slice(1).map((u, i) => (
                          <div key={i} style={{ marginTop: 2, opacity: 0.8 }}>{u}</div>
                        )) : (
                          <span onClick={() => setExpanded((p) => ({ ...p, [w.id]: true }))} style={{ cursor: 'pointer', fontSize: 11, color: '#999' }}>+{urls.length - 1} 个更多</span>
                        )}
                      </>
                    )}
                  </td>
                  <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{w.remark || '-'}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <button onClick={() => handleDelete(w.id, w.name)} style={{ fontSize: 11, padding: '4px 8px', color: '#e53935', border: '1px solid #e53935', background: 'none', borderRadius: 4, cursor: 'pointer' }}>删除</button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}

// ==================== Agent 状态 ====================

const SUB_AGENTS = [
  { key: 'orchestrator', label: '统筹 Agent', desc: '意图识别与任务分发', color: '#1976d2' },
  { key: 'analysis', label: '数据分析 Agent', desc: '数据集管理、统计分析、图表生成', color: '#7b1fa2' },
  { key: 'collection', label: '数据采集 Agent', desc: '网页爬取、数据抓取、内容提取', color: '#00695c' },
  { key: 'automation', label: '自动化 Agent', desc: '浏览器控制、题目审核、截图监控', color: '#e65100' },
]

function AgentsTab() {
  const [agents, setAgents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/agent-status`, { headers: headers() })
      const data = await safeJson(res)
      if (Array.isArray(data)) setAgents(data)
    } catch {}
    setLoading(false)
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [])

  if (loading) return <div style={{ textAlign: 'center', color: '#999', padding: 40 }}>加载中...</div>

  const mainOnline = agents.length > 0 && agents[0].online
  const mainAgent = agents[0]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* 统筹 Agent 运行状态 */}
      <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #eee', padding: '16px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <span style={{
            width: 10, height: 10, borderRadius: '50%',
            background: mainOnline ? '#4caf50' : '#ccc',
            display: 'inline-block',
          }} />
          <span style={{ fontWeight: 600, fontSize: 14, color: '#333' }}>
            {mainOnline ? 'Agent 运行中' : 'Agent 离线'}
          </span>
          <span style={{ fontSize: 12, color: '#999' }}>
            {mainOnline ? `${mainAgent?.agent_name || ''} @ ${mainAgent?.agent_id || ''}` : '请在本地启动 Agent'}
          </span>
          <div style={{ flex: 1 }} />
          <button onClick={load} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: '#1976d2' }}>刷新</button>
        </div>
        {!mainOnline && (
          <code style={{ display: 'block', marginTop: 8, background: '#f5f5f8', padding: '6px 10px', borderRadius: 4, fontSize: 12, color: '#666' }}>
            python agent/main.py --server-url ws://your-server:8000 --agent-id 1
          </code>
        )}
      </div>

      {/* 子 Agent 列表 */}
      <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #eee', overflow: 'hidden' }}>
        <div style={{ padding: '12px 20px', borderBottom: '1px solid #f0f0f0', fontWeight: 600, fontSize: 13, color: '#333', background: '#fafafa' }}>
          子 Agent 团队
        </div>
        {SUB_AGENTS.map((sa) => (
          <div key={sa.key} style={{
            display: 'flex', alignItems: 'center', gap: 12, padding: '12px 20px',
            borderBottom: '1px solid #f5f5f5',
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%', background: mainOnline ? sa.color : '#ddd',
              display: 'inline-block', flexShrink: 0,
            }} />
            <span style={{ fontWeight: 600, fontSize: 13, color: sa.color, minWidth: 120 }}>{sa.label}</span>
            <span style={{ fontSize: 12, color: '#999' }}>{sa.desc}</span>
            <div style={{ flex: 1 }} />
            <span style={{ fontSize: 11, color: mainOnline ? '#4caf50' : '#999' }}>
              {mainOnline ? '就绪' : '待连接'}
            </span>
          </div>
        ))}
      </div>

          {/* 实时活动 */}
          {agents.map((a, i) => {
            const acts = a.activities || []
            if (acts.length === 0) return null
            return (
              <div key={i} style={{ background: '#fff', borderRadius: 10, border: '1px solid #eee', padding: '12px 16px' }}>
                <h4 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 8px 0', color: '#333' }}>
                  {a.agent_name} 活动记录
                </h4>
                <div style={{ maxHeight: 240, overflow: 'auto' }}>
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
  )
}

// ==================== 模型配置 ====================

function ModelsTab() {
  const [models, setModels] = useState<Record<string, any>>({})

  useEffect(() => {
    fetch(`${API_BASE}/admin/models`, { headers: headers() })
      .then((r) => r.json()).then(setModels).catch(() => {})
  }, [])

  return (
    <div>
      <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, color: '#333' }}>已配置的模型</h3>
      <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #eee', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#f5f5f8' }}>
              {['模型 ID', '显示名', '供应商'].map((h) => (
                <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(models).map(([id, info]) => (
              <tr key={id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                <td style={{ padding: '10px 14px', fontFamily: 'monospace', fontSize: 12 }}>{id}</td>
                <td style={{ padding: '10px 14px' }}>{info.label as string}</td>
                <td style={{ padding: '10px 14px', color: '#666' }}>{info.provider as string}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ fontSize: 12, color: '#999', marginTop: 12 }}>
        模型配置在 <code>config/settings.py</code> 中修改。API Key 从本地 <code>.env</code> 文件读取。
      </p>
    </div>
  )
}

// ==================== 主组件 ====================

function AdminPageInner() {
  const [tab, setTab] = useState('dashboard')

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '24px 28px', gap: 16, overflow: 'auto', boxSizing: 'border-box', background: '#f8f9fb' }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0, color: '#2c2c54' }}>后台管理</h2>

      <div style={{ display: 'flex', gap: 6, borderBottom: '1px solid #e0e0e0', paddingBottom: 0, flexWrap: 'wrap' }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            style={{
              padding: '8px 18px', borderRadius: '8px 8px 0 0', border: 'none',
              background: tab === t.key ? '#fff' : 'transparent',
              color: tab === t.key ? '#333' : '#999',
              fontWeight: tab === t.key ? 600 : 400, fontSize: 13, cursor: 'pointer',
              borderBottom: tab === t.key ? '2px solid #1976d2' : '2px solid transparent',
              whiteSpace: 'nowrap',
            }}
          >{t.label}</button>
        ))}
      </div>

      <div style={{ flex: 1 }}>
        {tab === 'dashboard' && <DashboardTab />}
        {tab === 'users' && <UsersTab />}
        {tab === 'websites' && <WebsitesTab />}
        {tab === 'agents' && <AgentsTab />}
        {tab === 'models' && <ModelsTab />}
      </div>
    </div>
  )
}

export default function AdminPage() {
  return (
    <ErrorBoundary>
      <AdminPageInner />
    </ErrorBoundary>
  )
}
