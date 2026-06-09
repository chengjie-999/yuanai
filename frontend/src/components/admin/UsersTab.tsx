import { useState, useEffect, useMemo } from 'react'
import { Spinner, Empty, ErrorMsg, Card, btnPrimary, btnDangerSm, inputStyle, badge, headers, API_BASE } from './shared'
import { freezeUser } from '../../api'

export default function UsersTab() {
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
    try {
      const res = await fetch(`${API_BASE}/admin/users`, { headers: headers() })
      if (!res.ok) throw new Error()
      setUsers(await res.json())
    } catch { setError('获取用户列表失败') }
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
                const isAdminRole = u.role === 'admin'; const isFrozen = u.frozen
                return (
                  <tr key={u.id} style={{ borderBottom: '1px solid #f0f0f0', opacity: isFrozen ? 0.5 : 1 }}>
                    <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{u.id}</td>
                    <td style={{ padding: '10px 14px', color: '#333', fontWeight: 600 }}>{u.username}{isAdminRole && badge('管理员', '#1976d2')}{isFrozen && badge('已冻结', '#e53935')}</td>
                    <td style={{ padding: '10px 14px' }}>{isAdminRole ? <span style={{ color: '#1976d2', fontWeight: 600 }}>admin</span> : <span style={{ color: '#666' }}>user</span>}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: '#999' }}>{isFrozen ? `冻结至 ${u.frozen_until?.slice(0, 10)}` : '正常'}</td>
                    <td style={{ padding: '10px 14px', color: '#999', fontSize: 12 }}>{u.create_time?.slice(0, 10)}</td>
                    <td style={{ padding: '10px 14px' }}>
                      {!isAdminRole && <div style={{ display: 'flex', gap: 4 }}>
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
