import { useState, useEffect } from 'react'
import { API_BASE, getToken, fetchWebsites, addWebsite, deleteWebsite, fetchFiles, freezeUser, readFile } from '../api'

const TABS = [
  { key: 'users', label: '👤 用户管理' },
  { key: 'websites', label: '🌐 网站管理' },
  { key: 'files', label: '📁 文件管理' },
]

function headers() {
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  const t = getToken()
  if (t) h['Authorization'] = `Bearer ${t}`
  return h
}

// ==================== 用户管理 Tab ====================

function UsersTab() {
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
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

  if (loading) return <div style={{ textAlign: 'center', color: '#999', padding: 40 }}>加载中...</div>

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
          <button onClick={() => setShowCreate(true)} className="btn btn-primary btn-sm">+ 创建用户</button>
        ) : (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} placeholder="用户名" style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ddd', fontSize: 13, outline: 'none', width: 120 }} />
            <input value={newPassword} onChange={(e) => setNewPassword(e.target.value)} type="password" placeholder="密码" style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ddd', fontSize: 13, outline: 'none', width: 120 }} />
            <select value={newRole} onChange={(e) => setNewRole(e.target.value)} style={{ padding: '6px 8px', borderRadius: 4, border: '1px solid #ddd', fontSize: 13, outline: 'none' }}>
              <option value="user">user</option>
              <option value="admin">admin</option>
            </select>
            <button onClick={handleCreateUser} className="btn btn-primary btn-sm">确定</button>
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
                    {!isAdmin && (isFrozen ? (
                      <button onClick={() => handleFreeze(u.id, 0)} className="btn btn-outline btn-sm" style={{ fontSize: 11, padding: '4px 10px', color: '#388e3c', borderColor: '#388e3c' }}>解冻</button>
                    ) : (
                      <FreezeBtn userId={u.id} onFreeze={handleFreeze} />
                    ))}
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
  if (!open) return <button onClick={() => setOpen(true)} className="btn btn-outline-danger btn-sm" style={{ fontSize: 11, padding: '4px 10px' }}>冻结</button>
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
      <input type="number" min={1} max={365} value={days} onChange={(e) => setDays(Number(e.target.value))}
        style={{ width: 50, padding: '4px 6px', borderRadius: 4, border: '1px solid #ddd', fontSize: 11, outline: 'none' }} />
      <span style={{ fontSize: 11, color: '#999' }}>天</span>
      <button onClick={() => { onFreeze(userId, days); setOpen(false) }} className="btn btn-danger btn-sm" style={{ fontSize: 11, padding: '4px 8px' }}>确定</button>
      <button onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: '#999', padding: '2px 4px' }}>✕</button>
    </div>
  )
}

// ==================== 网站管理 Tab ====================

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
    // 逗号分隔多 URL，转为 JSON 数组
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
          <button onClick={() => setShowAdd(true)} className="btn btn-primary btn-sm">+ 添加网站</button>
        ) : (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="名称" style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ddd', fontSize: 13, outline: 'none', width: 120 }} />
            <input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="URL（多行用逗号分隔）" style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ddd', fontSize: 13, outline: 'none', width: 300 }} />
            <input value={newRemark} onChange={(e) => setNewRemark(e.target.value)} placeholder="备注（可选）" style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ddd', fontSize: 13, outline: 'none', width: 150 }} />
            <button onClick={handleAdd} className="btn btn-primary btn-sm">确定</button>
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
              <tr><td colSpan={4} style={{ padding: 30, textAlign: 'center', color: '#999' }}>暂无网站，点击上方添加</td></tr>
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
                          <span onClick={() => setExpanded((p) => ({ ...p, [w.id]: true }))}
                            style={{ cursor: 'pointer', fontSize: 11, color: '#999', display: 'inline-block', marginTop: 2 }}>
                            +{urls.length - 1} 个更多
                          </span>
                        )}
                        {isExpanded && (
                          <span onClick={() => setExpanded((p) => ({ ...p, [w.id]: false }))}
                            style={{ cursor: 'pointer', fontSize: 11, color: '#999', display: 'inline-block', marginTop: 2 }}>
                            ▲ 收起
                          </span>
                        )}
                      </>
                    )}
                  </td>
                  <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{w.remark || '-'}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <button onClick={() => handleDelete(w.id, w.name)} className="btn btn-outline-danger btn-sm" style={{ fontSize: 11, padding: '4px 8px' }}>删除</button>
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

// ==================== 文件管理 Tab ====================

function FilesTab() {
  const [dirs, setDirs] = useState<{ name: string; path: string; is_dir: boolean; size_kb: number }[]>([])
  const [currentPath, setCurrentPath] = useState('')
  const [loading, setLoading] = useState(true)
  const [preview, setPreview] = useState<{ type: string; data?: string; content?: string; detail?: string; name?: string; ext?: string } | null>(null)

  const load = async (p: string) => {
    setLoading(true)
    setCurrentPath(p)
    const data = await fetchFiles(p)
    setDirs(data.items || [])
    setLoading(false)
  }

  useEffect(() => { load('') }, [])

  const goUp = () => {
    const parts = currentPath.split(/[/\\]/).filter(Boolean)
    parts.pop()
    load(parts.join('/'))
  }

  const handleDoubleClick = async (d: { name: string; path: string; is_dir: boolean }) => {
    if (d.is_dir) return
    const res = await readFile(d.path)
    if (res.type === 'error') return
    setPreview({ ...res, name: d.name })
  }

  if (loading) return <div style={{ textAlign: 'center', color: '#999', padding: 40 }}>加载中...</div>
  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#666' }}>
        {currentPath && <button onClick={goUp} className="btn btn-outline btn-sm" style={{ fontSize: 11 }}>⬆ 上级</button>}
        <span>data/{currentPath || '.'}</span>
        <button onClick={() => load(currentPath)} className="btn btn-outline btn-sm" style={{ fontSize: 11 }}>🔄</button>
      </div>
      <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #eee', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#f5f5f8' }}>
              {['名称', '类型', '大小'].map((h) => (
                <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600, borderBottom: '2px solid #e0e0e0' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dirs.map((d, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #f0f0f0', cursor: d.is_dir ? 'pointer' : 'pointer' }}
                onClick={() => d.is_dir && load(d.path)}
                onDoubleClick={() => handleDoubleClick(d)}>
                <td style={{ padding: '10px 14px', color: d.is_dir ? '#1976d2' : '#333' }}>{d.is_dir ? '📁 ' : '📄 '}{d.name}</td>
                <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{d.is_dir ? '目录' : '文件'}</td>
                <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{d.is_dir ? '-' : `${d.size_kb} KB`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 文件预览弹窗 */}
      {preview && (
        <div onClick={() => setPreview(null)} style={{
          position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
        }}>
          <div onClick={(e) => e.stopPropagation()} style={{
            maxWidth: '80%', maxHeight: '85%', background: '#fff', borderRadius: 12,
            padding: 20, overflow: 'auto', cursor: 'default', minWidth: 300,
            boxShadow: '0 8px 40px rgba(0,0,0,0.2)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: '#333' }}>{preview.name}</span>
              <span onClick={() => setPreview(null)} style={{ cursor: 'pointer', fontSize: 18, color: '#999', lineHeight: 1 }}>✕</span>
            </div>
            {preview.type === 'image' && (
              <img src={`data:image/${preview.ext?.replace('.', '')};base64,${preview.data}`}
                style={{ maxWidth: '100%', maxHeight: '70vh', borderRadius: 6, display: 'block' }} />
            )}
            {preview.type === 'text' && (
              <pre style={{ background: '#f5f5f8', borderRadius: 8, padding: 16, fontSize: 13, lineHeight: 1.6, overflow: 'auto', maxHeight: '65vh', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{preview.content}</pre>
            )}
            {preview.type === 'unsupported' && (
              <div style={{ padding: 40, textAlign: 'center', color: '#999', fontSize: 14 }}>{preview.detail || '暂不支持预览'}</div>
            )}
            {preview.type === 'binary' && (
              <div style={{ padding: 40, textAlign: 'center', color: '#999', fontSize: 14 }}>{preview.detail || '二进制文件'}</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ==================== 主组件 ====================

export default function AdminPage() {
  const [tab, setTab] = useState('users')

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '24px 28px', gap: 16, overflow: 'auto', boxSizing: 'border-box', background: '#f8f9fb' }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0, color: '#2c2c54' }}>⚙ 后台管理</h2>

      <div style={{ display: 'flex', gap: 6, borderBottom: '1px solid #e0e0e0', paddingBottom: 0 }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            style={{
              padding: '8px 18px', borderRadius: '8px 8px 0 0', border: 'none',
              background: tab === t.key ? '#fff' : 'transparent',
              color: tab === t.key ? '#333' : '#999',
              fontWeight: tab === t.key ? 600 : 400, fontSize: 13, cursor: 'pointer',
              borderBottom: tab === t.key ? '2px solid #1976d2' : '2px solid transparent',
            }}
          >{t.label}</button>
        ))}
      </div>

      {tab === 'users' && <UsersTab />}
      {tab === 'websites' && <WebsitesTab />}
      {tab === 'files' && <FilesTab />}
    </div>
  )
}
