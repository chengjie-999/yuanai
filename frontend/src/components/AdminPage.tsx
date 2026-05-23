import { Component, useState, useEffect } from 'react'
import { API_BASE, getToken, fetchWebsites, addWebsite, deleteWebsite, freezeUser } from '../api'

const TABS = [
  { key: 'dashboard', label: '仪表盘' },
  { key: 'users', label: '用户管理' },
  { key: 'websites', label: '网站管理' },
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

function DashboardTab({ isAdmin }: { isAdmin: boolean }) {
  const [data, setData] = useState<any>(null)

  useEffect(() => {
    fetch(`${API_BASE}/admin/dashboard`, { headers: headers() })
      .then(safeJson).then((d) => { if (d && typeof d === 'object') setData(d) }).catch(() => {})
  }, [])

  const allCards = [
    { label: '用户数', value: data?.users ?? '-', color: '#42a5f5', adminOnly: true },
    { label: '会话数', value: data?.sessions ?? '-', color: '#66bb6a', adminOnly: true },
    { label: '消息数', value: data?.messages ?? '-', color: '#ffa726', adminOnly: true },
    { label: '今日消息', value: data?.today_messages ?? '-', color: '#ef5350', adminOnly: false },
    { label: '今日活跃', value: data?.today_users ?? '-', color: '#ab47bc', adminOnly: false },
    { label: '均消息/会话', value: data?.avg_messages ?? '-', color: '#26a69a', adminOnly: true },
    { label: '数据集', value: data?.datasets ?? '-', color: '#8d6e63', adminOnly: false },
  ]
  const cards = isAdmin ? allCards : allCards.filter((c) => !c.adminOnly)

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

      {isAdmin && data?.daily_messages?.length > 0 && (
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

// ==================== 文件管理 ====================

function FilesTab() {
  const [dirs, setDirs] = useState<{ name: string; path: string; is_dir: boolean; size_kb: number }[]>([])
  const [currentPath, setCurrentPath] = useState('')
  const [loading, setLoading] = useState(true)
  const [preview, setPreview] = useState<any>(null)

  const load = async (p: string) => {
    setLoading(true)
    setCurrentPath(p)
    fetch(`${API_BASE}/admin/files?path=` + encodeURIComponent(p), { headers: headers() })
      .then(safeJson).then((d) => { if (d && d.items) setDirs(d.items) }).catch(() => {})
    setLoading(false)
  }

  useEffect(() => { load('') }, [])

  const goUp = () => {
    const parts = currentPath.split(/[/\\]/).filter(Boolean)
    parts.pop()
    load(parts.join('/'))
  }

  const handlePreview = async (d: { name: string; path: string; is_dir: boolean }) => {
    if (d.is_dir) { load(d.path); return }
    fetch(`${API_BASE}/admin/file/read?path=` + encodeURIComponent(d.path), { headers: headers() })
      .then(safeJson).then((r: any) => setPreview({ ...r, name: d.name })).catch(() => {})
  }

  if (loading) return <div style={{ textAlign: 'center', color: '#999', padding: 40 }}>加载中...</div>
  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#666' }}>
        {currentPath && <button onClick={goUp} style={{ fontSize: 11, padding: '4px 8px', border: '1px solid #ddd', background: '#fff', borderRadius: 4, cursor: 'pointer' }}>上级</button>}
        <span>data/{currentPath || '.'}</span>
        <button onClick={() => load(currentPath)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: '#1976d2' }}>刷新</button>
      </div>
      <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #eee', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#f5f5f8' }}>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600 }}>名称</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600 }}>类型</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600 }}>大小</th>
            </tr>
          </thead>
          <tbody>
            {dirs.map((d, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #f0f0f0', cursor: 'pointer' }}
                onClick={() => handlePreview(d)}>
                <td style={{ padding: '10px 14px', color: d.is_dir ? '#1976d2' : '#333' }}>{d.is_dir ? 'DIR ' : 'FILE '}{d.name}</td>
                <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{d.is_dir ? '目录' : '文件'}</td>
                <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{d.is_dir ? '-' : `${d.size_kb} KB`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {preview && (
        <div onClick={() => setPreview(null)} style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: '80%', maxHeight: '85%', background: '#fff', borderRadius: 12, padding: 20, overflow: 'auto', minWidth: 300, boxShadow: '0 8px 40px rgba(0,0,0,0.2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: '#333' }}>{preview.name}</span>
              <span onClick={() => setPreview(null)} style={{ cursor: 'pointer', fontSize: 18, color: '#999' }}>x</span>
            </div>
            {preview.type === 'image' && <img src={`data:image/${preview.ext?.replace('.', '')};base64,${preview.data}`} style={{ maxWidth: '100%', borderRadius: 6 }} />}
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
  const visibleTabs = isAdmin ? TABS : TABS.filter((t) => t.key !== 'users' && t.key !== 'websites')

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '24px 28px', gap: 16, overflow: 'auto', boxSizing: 'border-box', background: '#f8f9fb' }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0, color: '#2c2c54' }}>后台管理</h2>

      <div style={{ display: 'flex', gap: 6, borderBottom: '1px solid #e0e0e0', paddingBottom: 0, flexWrap: 'wrap' }}>
        {visibleTabs.map((t) => (
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
        {tab === 'dashboard' && <DashboardTab isAdmin={isAdmin} />}
        {tab === 'users' && isAdmin && <UsersTab />}
        {tab === 'websites' && isAdmin && <WebsitesTab />}
        {tab === 'files' && isAdmin && <FilesTab />}

      </div>
    </div>
  )
}

export default function AdminPage({ isAdmin }: { isAdmin: boolean }) {
  return (
    <ErrorBoundary>
      <AdminPageInner isAdmin={isAdmin} />
    </ErrorBoundary>
  )
}
