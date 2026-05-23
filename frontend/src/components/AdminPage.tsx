import { Component, useState, useEffect, useMemo, useRef } from 'react'
import { API_BASE, getToken, fetchWebsites, addWebsite, deleteWebsite, freezeUser } from '../api'

const TABS = [
  { key: 'dashboard', label: '仪表盘' },
  { key: 'users', label: '用户管理' },
  { key: 'agents', label: 'Agent 状态' },
  { key: 'sessions', label: '会话记录' },
  { key: 'models', label: '模型配置' },
  { key: 'websites', label: '网站管理' },
  { key: 'datasets', label: '数据集' },
  { key: 'knowledge', label: '知识库' },
  { key: 'files', label: '文件管理' },
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

async function apiGet(path: string): Promise<any> {
  const res = await fetch(`${API_BASE}${path}`, { headers: headers() })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

async function apiPost(path: string, body?: any): Promise<any> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST', headers: headers(),
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

async function apiDelete(path: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE', headers: headers() })
  return res.ok
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

// ==================== 共享 UI ====================

const Spinner = () => <div style={{ textAlign: 'center', color: '#999', padding: 40, fontSize: 13 }}>加载中...</div>
const Empty = ({ msg = '暂无数据' }: { msg?: string }) => <div style={{ textAlign: 'center', color: '#bbb', padding: 40, fontSize: 13 }}>{msg}</div>
const ErrorMsg = ({ msg, onRetry }: { msg: string; onRetry?: () => void }) => (
  <div style={{ color: '#e53935', fontSize: 13, padding: 12, background: '#fff0f0', borderRadius: 8, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
    <span style={{ flex: 1 }}>{msg}</span>
    {onRetry && <button onClick={onRetry} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#1976d2', fontSize: 12, whiteSpace: 'nowrap' }}>重试</button>}
  </div>
)
const Card = ({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) => (
  <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #eee', overflow: 'hidden', ...style }}>{children}</div>
)
const CardHeader = ({ title, action }: { title: string; action?: React.ReactNode }) => (
  <div style={{ padding: '14px 20px', borderBottom: '1px solid #f0f0f0', fontWeight: 600, fontSize: 14, color: '#333', background: '#fafafa', display: 'flex', alignItems: 'center' }}>
    {title}<div style={{ flex: 1 }} />{action}
  </div>
)
const btnPrimary: React.CSSProperties = { background: '#1976d2', color: '#fff', border: 'none', borderRadius: 6, padding: '7px 16px', cursor: 'pointer', fontSize: 13, fontWeight: 500 }
const btnDangerSm: React.CSSProperties = { fontSize: 12, padding: '4px 10px', color: '#e53935', border: '1px solid #e53935', background: 'none', borderRadius: 4, cursor: 'pointer' }
const inputStyle: React.CSSProperties = { padding: '8px 12px', borderRadius: 6, border: '1px solid #ddd', fontSize: 13, outline: 'none', boxSizing: 'border-box' }
const badge = (text: string, color: string) => <span style={{ fontSize: 11, color, background: `${color}15`, padding: '2px 6px', borderRadius: 4, marginLeft: 6 }}>{text}</span>

// ==================== 仪表盘 ====================

function DashboardTab({ isAdmin }: { isAdmin: boolean }) {
  const [data, setData] = useState<any>(null)
  const [agents, setAgents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = () => {
    fetch(`${API_BASE}/admin/dashboard`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then((d) => { setData(d); setError('') })
      .catch((e) => setError(`仪表盘加载失败: ${e.message}`))
    fetch(`${API_BASE}/admin/agent-status`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((d) => { if (Array.isArray(d)) setAgents(d) })
      .catch(() => {})
    setLoading(false)
  }

  useEffect(() => { load(); const i = setInterval(load, 15000); return () => clearInterval(i) }, [])

  const onlineCount = agents.filter((a: any) => a.online).length
  const allCards = [
    { label: '用户数', value: data?.users ?? '-', color: '#42a5f5', adminOnly: true },
    { label: '会话数', value: data?.sessions ?? '-', color: '#66bb6a', adminOnly: true },
    { label: '消息数', value: data?.messages ?? '-', color: '#ffa726', adminOnly: true },
    { label: '在线 Agent', value: onlineCount, color: '#26c6da', adminOnly: false },
    { label: '今日消息', value: data?.today_messages ?? '-', color: '#ef5350', adminOnly: false },
    { label: '今日活跃', value: data?.today_users ?? '-', color: '#ab47bc', adminOnly: false },
    { label: '均消息/会话', value: data?.avg_messages ?? '-', color: '#26a69a', adminOnly: true },
    { label: '数据集', value: data?.datasets ?? '-', color: '#8d6e63', adminOnly: false },
  ]
  const cards = isAdmin ? allCards : allCards.filter((c) => !c.adminOnly)

  return (
    <div>
      {error && <ErrorMsg msg={error} onRetry={load} />}
      {loading && <Spinner />}
      {!loading && <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 12, marginBottom: 24 }}>
        {cards.map((c) => (
          <div key={c.label} style={{ background: '#fff', borderRadius: 12, border: '1px solid #eee', padding: '18px 16px', textAlign: 'center', transition: 'box-shadow 0.2s' }}
            onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 2px 12px rgba(0,0,0,0.06)')}
            onMouseLeave={(e) => (e.currentTarget.style.boxShadow = '')}>
            <div style={{ fontSize: 26, fontWeight: 700, color: c.color, lineHeight: 1.3 }}>{c.value}</div>
            <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>{c.label}</div>
          </div>
        ))}
      </div>
      {isAdmin && data?.daily_messages?.length > 0 && (
        <Card style={{ marginBottom: 24, padding: '20px 24px' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px', color: '#333' }}>近30天消息量</h3>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 100, padding: '0 4px' }}>
            {data.daily_messages.map((d: any, i: number) => {
              const max = Math.max(...data.daily_messages.map((x: any) => x.count), 1)
              const h = Math.max((d.count / max) * 80, d.count > 0 ? 4 : 0)
              return (
                <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '100%' }}>
                  <div style={{ width: '100%', maxWidth: 24, height: h, background: d.count > 0 ? 'linear-gradient(180deg, #42a5f5, #1e88e5)' : '#e8e8e8', borderRadius: '3px 3px 0 0', transition: 'opacity 0.15s', cursor: 'default', opacity: 0.75 }}
                    title={`${d.date}: ${d.count} 条`}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.75')} />
                </div>
              )
            })}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 10, color: '#bbb' }}>
            <span>{data.daily_messages[0]?.date}</span>
            <span>{data.daily_messages[data.daily_messages.length - 1]?.date}</span>
          </div>
        </Card>
      )}
      {agents.length > 0 && (
        <Card>
          <CardHeader title="Agent 在线状态" />
          {agents.map((a: any) => (
            <div key={a.agent_id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 20px', borderBottom: '1px solid #f5f5f5' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: a.online ? '#4caf50' : '#ccc', flexShrink: 0, boxShadow: a.online ? '0 0 6px rgba(76,175,80,0.5)' : undefined }} />
              <span style={{ fontWeight: 600, fontSize: 13, color: '#333' }}>{a.agent_name}</span>
              <span style={{ fontSize: 11, color: '#999', fontFamily: 'monospace' }}>ID: {a.agent_id}</span>
              <div style={{ flex: 1 }} />
              <span style={{ fontSize: 11, color: a.online ? '#4caf50' : '#999' }}>{a.online ? '在线' : '离线'}</span>
              {a.last_heartbeat && <span style={{ fontSize: 11, color: '#bbb' }}>{a.last_heartbeat}</span>}
            </div>
          ))}
        </Card>
      )}
      </>}
    </div>
  )
}

// ==================== 用户管理 ====================

function UsersTab() {
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState('user')

  const fetchUsers = async () => {
    setLoading(true); setError('')
    try { setUsers(await apiGet('/admin/users')) } catch { setError('获取用户列表失败') }
    setLoading(false)
  }
  useEffect(() => { fetchUsers() }, [])

  const filtered = useMemo(() => {
    if (!search.trim()) return users
    const q = search.toLowerCase()
    return users.filter((u) => u.username?.toLowerCase().includes(q) || String(u.id).includes(q))
  }, [users, search])

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
      const res = await fetch(`${API_BASE}/admin/users/create`, { method: 'POST', headers: headers(), body: JSON.stringify({ username: newUsername, password: newPassword, role: newRole }) })
      const data = await res.json()
      if (data.error) { setError(data.error); return }
      setShowCreate(false); setNewUsername(''); setNewPassword('')
      fetchUsers()
    } catch { setError('创建失败') }
  }

  return (
    <>
      {error && <ErrorMsg msg={error} onRetry={fetchUsers} />}
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        {!showCreate ? <button onClick={() => setShowCreate(true)} style={btnPrimary}>+ 创建用户</button> : (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} placeholder="用户名" style={{ ...inputStyle, width: 130 }} />
            <input value={newPassword} onChange={(e) => setNewPassword(e.target.value)} type="password" placeholder="密码" style={{ ...inputStyle, width: 130 }} />
            <select value={newRole} onChange={(e) => setNewRole(e.target.value)} style={{ padding: '8px 10px', borderRadius: 6, border: '1px solid #ddd', fontSize: 13, outline: 'none' }}>
              <option value="user">user</option><option value="admin">admin</option>
            </select>
            <button onClick={handleCreateUser} style={btnPrimary}>确定</button>
            <button onClick={() => setShowCreate(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: '#999' }}>取消</button>
          </div>
        )}
        <div style={{ flex: 1 }} />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜索用户名或 ID..." style={{ ...inputStyle, width: 200 }} />
      </div>
      {loading ? <Spinner /> : (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: '#f5f5f8' }}>
              {['ID', '用户名', '角色', '状态', '注册时间', '操作'].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600, borderBottom: '2px solid #e0e0e0' }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {filtered.length === 0 && <tr><td colSpan={6}><Empty msg={search ? '无匹配用户' : '暂无用户'} /></td></tr>}
              {filtered.map((u) => {
                const isAdmin = u.role === 'admin'; const isFrozen = u.frozen
                return (
                  <tr key={u.id} style={{ borderBottom: '1px solid #f0f0f0', opacity: isFrozen ? 0.5 : 1 }}>
                    <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{u.id}</td>
                    <td style={{ padding: '10px 14px', color: '#333', fontWeight: 600 }}>{u.username}{isAdmin && badge('管理员', '#1976d2')}{isFrozen && badge('已冻结', '#e53935')}</td>
                    <td style={{ padding: '10px 14px' }}>{isAdmin ? <span style={{ color: '#1976d2', fontWeight: 600 }}>admin</span> : <span style={{ color: '#666' }}>user</span>}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: '#999' }}>{isFrozen ? `冻结至 ${u.frozen_until?.slice(0, 10)}` : '正常'}</td>
                    <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{u.create_time?.slice(0, 10)}</td>
                    <td style={{ padding: '10px 14px' }}>
                      {!isAdmin && <div style={{ display: 'flex', gap: 4 }}>
                        {isFrozen ? <button onClick={() => handleFreeze(u.id, 0)} style={{ fontSize: 12, padding: '4px 10px', color: '#388e3c', border: '1px solid #388e3c', background: 'none', borderRadius: 4, cursor: 'pointer' }}>解冻</button> : <FreezeBtn userId={u.id} onFreeze={handleFreeze} />}
                        <button onClick={() => handleDeleteUser(u.id, u.username)} style={btnDangerSm}>删除</button>
                      </div>}
                    </td>
                  </tr>)
              })}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}

function FreezeBtn({ userId, onFreeze }: { userId: number; onFreeze: (id: number, days: number) => void }) {
  const [open, setOpen] = useState(false); const [days, setDays] = useState(7)
  if (!open) return <button onClick={() => setOpen(true)} style={{ fontSize: 12, padding: '4px 10px', color: '#e53935', border: '1px solid #e53935', background: 'none', borderRadius: 4, cursor: 'pointer' }}>冻结</button>
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
      <input type="number" min={1} max={365} value={days} onChange={(e) => setDays(Number(e.target.value))} style={{ width: 48, padding: '4px 6px', borderRadius: 4, border: '1px solid #ddd', fontSize: 12, outline: 'none' }} />
      <span style={{ fontSize: 11, color: '#999' }}>天</span>
      <button onClick={() => { onFreeze(userId, days); setOpen(false) }} style={{ fontSize: 11, padding: '4px 8px', color: '#fff', background: '#e53935', border: 'none', borderRadius: 4, cursor: 'pointer' }}>确定</button>
      <button onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: '#999', padding: '2px 4px' }}>✕</button>
    </div>
  )
}

// ==================== Agent 全局状态 ====================

const SUB_AGENTS = [
  { key: 'orchestrator', label: '统筹 Agent', desc: '意图识别与任务分发', color: '#1976d2' },
  { key: 'analysis', label: '数据分析 Agent', desc: '数据集管理、统计分析、图表生成', color: '#7b1fa2' },
  { key: 'collection', label: '数据采集 Agent', desc: '网页爬取、数据抓取、内容提取', color: '#00695c' },
  { key: 'automation', label: '自动化 Agent', desc: '浏览器控制、题目审核、截图监控', color: '#e65100' },
]

function AgentsTab() {
  const [agents, setAgents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = () => {
    fetch(`${API_BASE}/admin/agent-status`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((d) => { if (Array.isArray(d)) { setAgents(d); setError('') } })
      .catch(() => setError('加载 Agent 状态失败'))
    setLoading(false)
  }
  useEffect(() => { load(); const i = setInterval(load, 10000); return () => clearInterval(i) }, [])

  const online = agents.filter((a) => a.online)
  const offline = agents.filter((a) => !a.online)
  const allActivities = agents.flatMap((a) => (a.activities || []).map((act: any) => ({ ...act, agent: a.agent_name, agentId: a.agent_id })))
    .sort((a: any, b: any) => (b.time || '').localeCompare(a.time || '')).slice(0, 20)

  if (loading) return <Spinner />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {error && <ErrorMsg msg={error} onRetry={load} />}

      {/* 概览统计 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        {[
          { label: 'Agent 总数', value: agents.length, color: '#1976d2' },
          { label: '在线', value: online.length, color: '#4caf50' },
          { label: '离线', value: offline.length, color: '#ccc' },
          { label: '子 Agent 类型', value: SUB_AGENTS.length, color: '#ff9800' },
        ].map((c) => (
          <div key={c.label} style={{ background: '#fff', borderRadius: 10, border: '1px solid #eee', padding: '14px 16px', textAlign: 'center' }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: c.color }}>{c.value}</div>
            <div style={{ fontSize: 12, color: '#999', marginTop: 2 }}>{c.label}</div>
          </div>
        ))}
      </div>

      {/* Agent 列表 */}
      <Card>
        <CardHeader title={`Agent 列表 (${agents.length})`} action={<button onClick={load} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: '#1976d2' }}>刷新</button>} />
        {agents.length === 0 ? <Empty msg="暂无 Agent 连接" /> : (
          agents.map((a) => (
            <div key={a.agent_id} style={{ padding: '14px 20px', borderBottom: '1px solid #f5f5f5', display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: a.online ? '#4caf50' : '#ccc', flexShrink: 0, boxShadow: a.online ? '0 0 8px rgba(76,175,80,0.4)' : undefined }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: a.online ? '#333' : '#999' }}>{a.agent_name}</div>
                <div style={{ fontSize: 12, color: '#999', marginTop: 2 }}>ID: {a.agent_id}{a.last_heartbeat && <span style={{ marginLeft: 12 }}>心跳: {a.last_heartbeat}</span>}</div>
              </div>
              <span style={{ fontSize: 12, fontWeight: 600, color: a.online ? '#4caf50' : '#999' }}>{a.online ? '在线' : '离线'}</span>
            </div>
          ))
        )}
      </Card>

      {/* 子 Agent 团队 */}
      <Card>
        <CardHeader title="子 Agent 团队" />
        {SUB_AGENTS.map((sa) => (
          <div key={sa.key} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 20px', borderBottom: '1px solid #f5f5f5' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: online.length > 0 ? sa.color : '#ddd', flexShrink: 0 }} />
            <div><div style={{ fontWeight: 600, fontSize: 13, color: sa.color }}>{sa.label}</div><div style={{ fontSize: 12, color: '#999', marginTop: 1 }}>{sa.desc}</div></div>
            <div style={{ flex: 1 }} />
            <span style={{ fontSize: 11, color: online.length > 0 ? '#4caf50' : '#999' }}>{online.length > 0 ? '就绪' : '待连接'}</span>
          </div>
        ))}
      </Card>

      {/* 全局活动流 */}
      {allActivities.length > 0 && (
        <Card>
          <CardHeader title="全局活动记录" />
          <div style={{ maxHeight: 300, overflow: 'auto' }}>
            {allActivities.map((act: any, j: number) => (
              <div key={j} style={{ padding: '8px 20px', borderBottom: j < allActivities.length - 1 ? '1px solid #f5f5f5' : 'none', display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <span style={{ fontSize: 11, color: '#bbb', minWidth: 52, flexShrink: 0 }}>{act.time}</span>
                <span style={{ fontSize: 11, color: '#1976d2', minWidth: 80, flexShrink: 0 }}>[{act.agent}]</span>
                <span style={{ fontSize: 13, color: '#333' }}>{act.message}</span>
                {act.detail && <span style={{ fontSize: 11, color: '#999' }}>{act.detail}</span>}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

// ==================== 会话记录 ====================

function SessionsTab() {
  const [sessions, setSessions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')

  const load = () => {
    setError('')
    fetch(`${API_BASE}/chat/sessions`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then((d) => { if (Array.isArray(d)) setSessions(d) })
      .catch((e) => setError(`加载会话列表失败: ${e.message}`))
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  const handleDelete = async (id: string) => {
    if (!confirm('确认删除此会话？')) return
    if (await apiDelete(`/chat/session/${id}`)) load()
  }

  const filtered = search.trim()
    ? sessions.filter((s) => s.title?.toLowerCase().includes(search.toLowerCase()) || s.session_id?.includes(search) || s.username?.toLowerCase().includes(search.toLowerCase()))
    : sessions

  return (
    <>
      {error && <ErrorMsg msg={error} onRetry={load} />}
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, alignItems: 'center' }}>
        <div style={{ flex: 1 }} />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜索标题、用户或 ID..." style={{ ...inputStyle, width: 240 }} />
      </div>
      {loading ? <Spinner /> : (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: '#f5f5f8' }}>
              {['会话 ID', '标题', '用户', '消息数', '创建时间', '更新时间', '操作'].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600, borderBottom: '2px solid #e0e0e0' }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {filtered.length === 0 && <tr><td colSpan={7}><Empty msg={search ? '无匹配会话' : '暂无会话'} /></td></tr>}
              {filtered.map((s) => (
                <tr key={s.session_id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '10px 14px', fontFamily: 'monospace', fontSize: 11, color: '#888', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={s.session_id}>{s.session_id.slice(0, 12)}...</td>
                  <td style={{ padding: '10px 14px', fontWeight: 600, color: '#333', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.title || '未命名'}</td>
                  <td style={{ padding: '10px 14px', color: '#666', fontSize: 12 }}>{s.username}</td>
                  <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{s.message_count ?? '-'}</td>
                  <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{s.create_time?.slice(0, 16)}</td>
                  <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{s.update_time?.slice(0, 16)}</td>
                  <td style={{ padding: '10px 14px' }}><button onClick={() => handleDelete(s.session_id)} style={btnDangerSm}>删除</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}

// ==================== 模型配置 ====================

function ModelsTab() {
  const [models, setModels] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [newId, setNewId] = useState(''); const [newLabel, setNewLabel] = useState('')
  const [newProvider, setNewProvider] = useState('Custom'); const [newKey, setNewKey] = useState('')

  const loadModels = () => {
    setError('')
    fetch(`${API_BASE}/admin/models`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((data) => { if (data && typeof data === 'object' && !Array.isArray(data)) setModels(data) })
      .catch(() => setError('加载模型配置失败'))
    setLoading(false)
  }
  useEffect(() => { loadModels() }, [])

  const handleAdd = async () => {
    if (!newId.trim() || !newLabel.trim()) return
    setError('')
    const res = await fetch(`${API_BASE}/admin/models`, { method: 'POST', headers: headers(), body: JSON.stringify({ model_id: newId.trim(), label: newLabel.trim(), provider: newProvider.trim() || 'Custom' }) })
    if (!res.ok) { const d = await safeJson(res); setError(d?.detail || '添加失败'); return }
    if (newKey.trim()) { await fetch(`${API_BASE}/admin/apikeys`, { method: 'POST', headers: headers(), body: JSON.stringify({ provider: newProvider.trim() || 'Custom', key: newKey.trim() }) }) }
    setShowModal(false); setNewId(''); setNewLabel(''); setNewProvider('Custom'); setNewKey('')
    loadModels()
  }
  const handleDelete = async (id: string) => {
    if (!confirm(`确定删除模型 "${id}"？`)) return
    setError('')
    const res = await fetch(`${API_BASE}/admin/models`, { method: 'DELETE', headers: headers(), body: JSON.stringify({ model_id: id }) })
    if (!res.ok) { const d = await safeJson(res); setError(d?.detail || '删除失败'); return }
    loadModels()
  }
  const entries = Object.entries(models)

  return (
    <>
      {error && <ErrorMsg msg={error} onRetry={loadModels} />}
      {loading ? <Spinner /> : (
        <Card>
          <CardHeader title="模型配置" action={<button onClick={() => setShowModal(true)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: '#1976d2', fontWeight: 500 }}>+ 添加</button>} />
          {entries.length === 0 ? <Empty msg="暂无模型配置" /> : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead><tr style={{ background: '#f5f5f8' }}>
                {['用途', '模型 ID', '供应商', ''].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666' }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {entries.map(([id, info]) => {
                  if (!info || typeof info !== 'object') return null
                  const label = (info as any).label; if (!label) return null
                  const desc = id.includes('deepseek') ? (label.includes('Pro') ? '强推理' : '快速轻量') : label.includes('Pro') ? '多模态/强推理' : '轻量任务'
                  return (
                    <tr key={id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                      <td style={{ padding: '10px 14px', fontSize: 13, fontWeight: 500 }}>{label}<span style={{ fontSize: 11, color: '#999', marginLeft: 6 }}>{desc}</span></td>
                      <td style={{ padding: '10px 14px', fontFamily: 'monospace', fontSize: 11, color: '#888' }}>{id}</td>
                      <td style={{ padding: '10px 14px', color: '#666', fontSize: 12 }}>{info.provider as string}</td>
                      <td style={{ padding: '10px 14px' }}>{!info.builtin && <button onClick={() => handleDelete(id)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: '#ccc', padding: 0 }}>x</button>}</td>
                    </tr>)
                })}
              </tbody>
            </table>
          )}
        </Card>
      )}
      {showModal && (
        <div onClick={() => setShowModal(false)} style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: '#fff', borderRadius: 12, padding: 24, minWidth: 380, boxShadow: '0 8px 40px rgba(0,0,0,0.15)' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 600, color: '#333' }}>添加模型</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <input value={newId} onChange={(e) => setNewId(e.target.value)} placeholder="模型 ID (如 gpt-4)" style={inputStyle} />
              <input value={newLabel} onChange={(e) => setNewLabel(e.target.value)} placeholder="显示名 (如 GPT-4)" style={inputStyle} />
              <input value={newProvider} onChange={(e) => setNewProvider(e.target.value)} placeholder="供应商 (如 OpenAI)" style={inputStyle} />
              <input value={newKey} onChange={(e) => setNewKey(e.target.value)} placeholder="API Key (可选)" style={inputStyle} />
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowModal(false)} style={{ padding: '6px 16px', borderRadius: 6, border: '1px solid #ddd', background: '#fff', cursor: 'pointer', fontSize: 13, color: '#666' }}>取消</button>
              <button onClick={handleAdd} style={btnPrimary}>确认添加</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

// ==================== 网站管理 ====================

function WebsitesTab() {
  const [websites, setWebsites] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [newName, setNewName] = useState(''); const [newUrl, setNewUrl] = useState(''); const [newRemark, setNewRemark] = useState('')
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})

  const parseUrls = (w: any): string[] => {
    if (Array.isArray(w.url)) return w.url
    if (typeof w.url === 'string') { try { const j = JSON.parse(w.url); return Array.isArray(j) ? j : [w.url] } catch { return [w.url] } }
    return [String(w.url)]
  }
  const load = async () => { setLoading(true); setError(''); setWebsites(await fetchWebsites()); setLoading(false) }
  useEffect(() => { load() }, [])

  const handleAdd = async () => {
    if (!newName.trim() || !newUrl.trim()) return
    const urls = newUrl.split(/[,，]/).map((u) => u.trim()).filter(Boolean)
    const r = await addWebsite(newName, JSON.stringify(urls), newRemark)
    if (r.error) { setError(r.error); return }
    setShowAdd(false); setNewName(''); setNewUrl(''); setNewRemark(''); setError(''); load()
  }
  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`确定删除网站 "${name}"？`)) return
    if (await deleteWebsite(id)) load()
  }

  return (
    <>
      {error && <ErrorMsg msg={error} />}
      <div style={{ marginBottom: 12 }}>
        {!showAdd ? <button onClick={() => setShowAdd(true)} style={btnPrimary}>+ 添加网站</button> : (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="名称" style={{ ...inputStyle, width: 130 }} />
            <input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="URL（多个用逗号分隔）" style={{ ...inputStyle, width: 320 }} />
            <input value={newRemark} onChange={(e) => setNewRemark(e.target.value)} placeholder="备注（可选）" style={{ ...inputStyle, width: 150 }} />
            <button onClick={handleAdd} style={btnPrimary}>确定</button>
            <button onClick={() => setShowAdd(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: '#999' }}>取消</button>
          </div>
        )}
      </div>
      {loading ? <Spinner /> : (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: '#f5f5f8' }}>
              {['名称', 'URL', '备注', '操作'].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600, borderBottom: '2px solid #e0e0e0' }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {websites.length === 0 && <tr><td colSpan={4}><Empty msg="暂无网站" /></td></tr>}
              {websites.map((w) => {
                const urls = parseUrls(w); const isExpanded = expanded[w.id]
                return (
                  <tr key={w.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 600, color: '#333' }}>{w.name}</td>
                    <td style={{ padding: '10px 14px', color: '#1976d2', fontSize: 12 }}>
                      <div style={{ wordBreak: 'break-all' }}>{urls[0]}</div>
                      {urls.length > 1 && (isExpanded ? urls.slice(1).map((u, i) => <div key={i} style={{ marginTop: 2, opacity: 0.8, wordBreak: 'break-all' }}>{u}</div>) : <span onClick={() => setExpanded((p) => ({ ...p, [w.id]: true }))} style={{ cursor: 'pointer', fontSize: 11, color: '#999' }}>+{urls.length - 1} 个更多</span>)}
                    </td>
                    <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{w.remark || '-'}</td>
                    <td style={{ padding: '10px 14px' }}><button onClick={() => handleDelete(w.id, w.name)} style={btnDangerSm}>删除</button></td>
                  </tr>)
              })}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}

// ==================== 数据集 ====================

function DatasetsTab() {
  const [datasets, setDatasets] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [preview, setPreview] = useState<any>(null)
  const [analysis, setAnalysis] = useState<any>(null)
  const [analyzing, setAnalyzing] = useState(false)

  const load = () => {
    setError('')
    fetch(`${API_BASE}/data/datasets`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((d) => { if (Array.isArray(d)) setDatasets(d) })
      .catch(() => setError('加载数据集失败'))
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  const handleDelete = async (id: number) => {
    if (!confirm('确认删除此数据集？')) return
    if (await apiDelete(`/data/dataset/${id}`)) load()
  }

  const handleAnalyze = async (id: number) => {
    setAnalyzing(true); setError('')
    try {
      const d = await apiGet(`/data/analyze/${id}?charts=true&force=true`)
      setAnalysis(d)
    } catch { setError('分析失败') }
    setAnalyzing(false)
  }

  return (
    <>
      {error && <ErrorMsg msg={error} onRetry={load} />}
      {loading ? <Spinner /> : datasets.length === 0 ? <Empty msg="暂无数据集" /> : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Card>
            <CardHeader title={`数据集 (${datasets.length})`} />
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead><tr style={{ background: '#f5f5f8' }}>
                {['名称', '类型', '大小', '行数', '上传时间', '操作'].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600, borderBottom: '2px solid #e0e0e0' }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {datasets.map((d: any) => (
                  <tr key={d.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 600, color: '#333', cursor: 'pointer' }} onClick={() => setPreview(d)}>{d.name}</td>
                    <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{d.file_type}</td>
                    <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{d.file_size ? `${(d.file_size / 1024).toFixed(1)} KB` : '-'}</td>
                    <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{d.row_count ?? '-'}</td>
                    <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{d.create_time?.slice(0, 16)}</td>
                    <td style={{ padding: '10px 14px', display: 'flex', gap: 6 }}>
                      <button onClick={() => handleAnalyze(d.id)} disabled={analyzing} style={{ fontSize: 12, padding: '4px 10px', color: '#1976d2', border: '1px solid #1976d2', background: 'none', borderRadius: 4, cursor: 'pointer' }}>{analyzing ? '分析中...' : '分析'}</button>
                      <button onClick={() => handleDelete(d.id)} style={btnDangerSm}>删除</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          {preview && preview.preview_rows && (
            <Card>
              <CardHeader title={`预览: ${preview.name}`} action={<button onClick={() => setPreview(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: '#999' }}>关闭</button>} />
              <div style={{ overflow: 'auto', maxHeight: 300 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead><tr>
                    {preview.columns?.map((c: any) => <th key={c.name} style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: '#666', background: '#f5f5f8', borderBottom: '2px solid #e0e0e0', whiteSpace: 'nowrap' }}>{c.name}</th>)}
                  </tr></thead>
                  <tbody>
                    {preview.preview_rows.slice(0, 50).map((row: any, i: number) => (
                      <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
                        {preview.columns?.map((c: any) => <td key={c.name} style={{ padding: '6px 12px', color: '#333', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{String(row[c.name] ?? '')}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {analysis && (
            <Card>
              <CardHeader title={`分析结果: ${analysis.dataset_name || ''}`} action={<button onClick={() => setAnalysis(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: '#999' }}>关闭</button>} />
              <div style={{ padding: 16 }}>
                {analysis.summary && Object.entries(analysis.summary).map(([k, v]: [string, any]) => {
                  let val = '-'
                  if (typeof v === 'number') {
                    val = Number.isInteger(v) ? String(v) : v.toFixed(2)
                  } else if (typeof v === 'object') {
                    val = JSON.stringify(v)
                  } else {
                    val = String(v)
                  }
                  return (
                    <div key={k} style={{ display: 'flex', padding: '6px 0', borderBottom: '1px solid #f5f5f5' }}>
                      <span style={{ fontWeight: 600, fontSize: 13, color: '#333', minWidth: 160 }}>{k}</span>
                      <span style={{ fontSize: 13, color: '#666' }}>{val}</span>
                    </div>
                  )
                })}
                {analysis.text && <pre style={{ marginTop: 12, background: '#f5f5f8', borderRadius: 8, padding: 16, fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{analysis.text}</pre>}
                {analysis.charts?.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 16 }}>
                    {analysis.charts.map((name: string, i: number) => (
                      <img key={i} src={`${API_BASE}/data/analysis-image/${analysis.dataset_id}/${name}`} alt={name} style={{ maxWidth: '100%', borderRadius: 8, border: '1px solid #eee' }} />
                    ))}
                  </div>
                )}
              </div>
            </Card>
          )}
        </div>
      )}
    </>
  )
}

// ==================== 知识库 ====================

function KnowledgeTab() {
  const [sources, setSources] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [searchQ, setSearchQ] = useState('')
  const [searchResult, setSearchResult] = useState<any>(null)
  const [searching, setSearching] = useState(false)
  const [rebuilding, setRebuilding] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = () => {
    setError('')
    fetch(`${API_BASE}/knowledge/sources`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((d) => { if (Array.isArray(d)) setSources(d) })
      .catch(() => setError('加载知识库失败'))
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return
    setError('')
    const form = new FormData(); form.append('file', file); form.append('visibility', 'shared')
    const res = await fetch(`${API_BASE}/knowledge/upload`, { method: 'POST', headers: { Authorization: headers()['Authorization'] }, body: form })
    if (!res.ok) { const d = await safeJson(res); setError(d?.detail || '上传失败'); return }
    load()
  }

  const handleDelete = async (source: string) => {
    if (!confirm(`确定删除知识源 "${source}"？`)) return
    if (await apiDelete(`/knowledge/${source}`)) load()
  }

  const handleRebuild = async () => {
    if (!confirm('确定全量重建知识库？此操作可能需要几分钟。')) return
    setRebuilding(true); setError('')
    try { await apiPost('/knowledge/rebuild'); load() }
    catch { setError('重建失败') }
    setRebuilding(false)
  }

  const handleSearch = async () => {
    if (!searchQ.trim()) return
    setSearching(true); setError('')
    try { setSearchResult(await apiGet(`/knowledge/search?q=${encodeURIComponent(searchQ.trim())}`)) }
    catch { setError('检索失败') }
    setSearching(false)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {error && <ErrorMsg msg={error} onRetry={load} />}

      {/* 搜索 */}
      <Card>
        <CardHeader title="知识库检索" />
        <div style={{ padding: '12px 20px', display: 'flex', gap: 8 }}>
          <input value={searchQ} onChange={(e) => setSearchQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSearch()} placeholder="输入关键词检索知识库..." style={{ ...inputStyle, flex: 1 }} />
          <button onClick={handleSearch} disabled={searching} style={btnPrimary}>{searching ? '检索中...' : '搜索'}</button>
        </div>
        {searchResult && (
          <div style={{ maxHeight: 400, overflow: 'auto', padding: '0 20px 16px' }}>
            {searchResult.results?.length > 0 ? searchResult.results.map((r: any, i: number) => (
              <div key={i} style={{ padding: '10px 0', borderBottom: '1px solid #f0f0f0' }}>
                <div style={{ fontSize: 12, color: '#1976d2', marginBottom: 4 }}>来源: {r.source} | 相似度: {(r.score * 100).toFixed(0)}%</div>
                <div style={{ fontSize: 13, color: '#333', lineHeight: 1.6 }}>{r.content}</div>
              </div>
            )) : <Empty msg="无匹配结果" />}
          </div>
        )}
      </Card>

      {/* 知识源列表 */}
      {loading ? <Spinner /> : (
        <Card>
          <CardHeader title={`知识源 (${sources.length})`} action={
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => fileRef.current?.click()} style={{ ...btnPrimary, fontSize: 12, padding: '5px 12px' }}>+ 上传 ZIP</button>
              <button onClick={handleRebuild} disabled={rebuilding} style={{ fontSize: 12, padding: '5px 12px', color: '#e53935', border: '1px solid #e53935', background: 'none', borderRadius: 6, cursor: 'pointer' }}>{rebuilding ? '重建中...' : '重建索引'}</button>
              <input ref={fileRef} type="file" accept=".zip" onChange={handleUpload} style={{ display: 'none' }} />
            </div>
          } />
          {sources.length === 0 ? <Empty msg="暂无知识源" /> : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead><tr style={{ background: '#f5f5f8' }}>
                {['名称', '分块数', '图片数', '可见性', '操作'].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600, borderBottom: '2px solid #e0e0e0' }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {sources.map((s) => (
                  <tr key={s.source} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 600, color: '#333', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={s.source}>{s.source}</td>
                    <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{s.chunks}</td>
                    <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{s.images}</td>
                    <td style={{ padding: '10px 14px' }}>{s.visibility === 'shared' ? badge('共享', '#4caf50') : badge('私有', '#ff9800')}</td>
                    <td style={{ padding: '10px 14px' }}><button onClick={() => handleDelete(s.source)} style={btnDangerSm}>删除</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}
    </div>
  )
}

// ==================== 文件管理 ====================

function FilesTab() {
  const [dirs, setDirs] = useState<{ name: string; path: string; is_dir: boolean; size_kb: number }[]>([])
  const [currentPath, setCurrentPath] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [preview, setPreview] = useState<any>(null)

  const load = async (p: string) => {
    setLoading(true); setError(''); setCurrentPath(p)
    try {
      const res = await fetch(`${API_BASE}/admin/files?path=` + encodeURIComponent(p), { headers: headers() })
      const d = await safeJson(res)
      if (d && d.items) setDirs(d.items); else if (d && d.error) setError(d.error)
    } catch { setError('加载文件列表失败') }
    setLoading(false)
  }
  useEffect(() => { load('') }, [])

  const goUp = () => { const parts = currentPath.split(/[/\\]/).filter(Boolean); parts.pop(); load(parts.join('/')) }

  const handlePreview = async (d: { name: string; path: string; is_dir: boolean }) => {
    if (d.is_dir) { load(d.path); return }
    setError('')
    try {
      const res = await fetch(`${API_BASE}/admin/file/read?path=` + encodeURIComponent(d.path), { headers: headers() })
      const r = await safeJson(res)
      if (r && r.error) { setError(r.error); return }
      setPreview({ ...r, name: d.name })
    } catch { setError('读取文件失败') }
  }

  return (
    <div>
      {error && <ErrorMsg msg={error} />}
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#666' }}>
        {currentPath && <button onClick={goUp} style={{ fontSize: 12, padding: '4px 10px', border: '1px solid #ddd', background: '#fff', borderRadius: 4, cursor: 'pointer' }}>上级目录</button>}
        <span style={{ fontFamily: 'monospace', fontSize: 12 }}>data/{currentPath || '.'}</span>
        <button onClick={() => load(currentPath)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: '#1976d2' }}>刷新</button>
      </div>
      {loading ? <Spinner /> : (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: '#f5f5f8' }}>
              {['名称', '类型', '大小'].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600 }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {dirs.length === 0 && <tr><td colSpan={3}><Empty msg="空目录" /></td></tr>}
              {dirs.map((d, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #f0f0f0', cursor: 'pointer', transition: 'background 0.1s' }}
                  onClick={() => handlePreview(d)}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#fafafa')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = '')}>
                  <td style={{ padding: '10px 14px', color: d.is_dir ? '#1976d2' : '#333', fontWeight: d.is_dir ? 600 : 400 }}>{d.is_dir ? '📁 ' : '📄 '}{d.name}</td>
                  <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{d.is_dir ? '目录' : '文件'}</td>
                  <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{d.is_dir ? '-' : `${d.size_kb} KB`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {preview && (
        <div onClick={() => setPreview(null)} style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: '80%', maxHeight: '85%', background: '#fff', borderRadius: 12, padding: 24, overflow: 'auto', minWidth: 360, boxShadow: '0 8px 40px rgba(0,0,0,0.2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: '#333' }}>{preview.name}</span>
              <span onClick={() => setPreview(null)} style={{ cursor: 'pointer', fontSize: 18, color: '#999', lineHeight: 1 }}>✕</span>
            </div>
            {preview.type === 'image' && <img src={`data:image/${preview.ext?.replace('.', '')};base64,${preview.data}`} style={{ maxWidth: '100%', borderRadius: 8 }} />}
            {preview.type === 'text' && <pre style={{ background: '#f5f5f8', borderRadius: 8, padding: 16, fontSize: 13, lineHeight: 1.6, overflow: 'auto', maxHeight: '65vh', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{preview.content}</pre>}
            {!preview.type && <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>{preview.detail || '无法预览'}</div>}
          </div>
        </div>
      )}
    </div>
  )
}

// ==================== 主组件 ====================

function AdminPageInner({ isAdmin }: { isAdmin: boolean }) {
  const [tab, setTab] = useState('dashboard')

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '24px 28px', gap: 20, overflow: 'auto', boxSizing: 'border-box', background: '#f8f9fb' }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: '#1a1a2e' }}>后台管理</h2>
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid #e8e8ec', paddingBottom: 0, flexWrap: 'wrap' }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} style={{
            padding: '9px 16px', borderRadius: '8px 8px 0 0', border: 'none',
            background: tab === t.key ? '#fff' : 'transparent',
            color: tab === t.key ? '#1976d2' : '#888',
            fontWeight: tab === t.key ? 600 : 400, fontSize: 13, cursor: 'pointer',
            borderBottom: tab === t.key ? '2px solid #1976d2' : '2px solid transparent',
            whiteSpace: 'nowrap', transition: 'color 0.15s, border-color 0.15s',
          }}>{t.label}</button>
        ))}
      </div>
      <div style={{ flex: 1 }}>
        {tab === 'dashboard' && <DashboardTab isAdmin={isAdmin} />}
        {tab === 'users' && <UsersTab />}
        {tab === 'agents' && <AgentsTab />}
        {tab === 'sessions' && <SessionsTab />}
        {tab === 'models' && <ModelsTab />}
        {tab === 'websites' && <WebsitesTab />}
        {tab === 'datasets' && <DatasetsTab />}
        {tab === 'knowledge' && <KnowledgeTab />}
        {tab === 'files' && <FilesTab />}
      </div>
    </div>
  )
}

export default function AdminPage({ isAdmin }: { isAdmin: boolean }) {
  return <ErrorBoundary><AdminPageInner isAdmin={isAdmin} /></ErrorBoundary>
}
