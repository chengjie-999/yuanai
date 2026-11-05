import { useState, useEffect, useMemo } from 'react'
import { Spinner, Empty, ErrorMsg, Card, btnPrimary, btnDangerSm, inputStyle, badge, headers, API_BASE, fmtCost, fmtCostNeg4, fmtCostSigned } from './shared'
import { freezeUser } from '../../api'
import { XIcon } from '../icons'
import Modal from '../Modal'

// detail 归一化（2026-10-30）：pydantic 422 的 detail 是数组——直接 setError 会
// 渲染对象数组崩溃；取第一条 msg，string 直用，数组兜底「请求参数错误」
const _detail = (d: any): string => {
  const detail = d?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) return typeof detail[0]?.msg === 'string' ? detail[0].msg : '请求参数错误'
  return d?.error || ''
}

export default function UsersTab() {
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newPassword2, setNewPassword2] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [newRole, setNewRole] = useState('user')
  const [notice, setNotice] = useState('')

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
    return users.filter((u) => u.username?.toLowerCase().includes(q)
      || u.display_name?.toLowerCase().includes(q)
      || u.email?.toLowerCase().includes(q)
      || String(u.id).includes(q))
  }, [users, search])

  const handleFreeze = async (userId: number, days: number, reason: string = '') => {
    setError('')
    const data = await freezeUser(userId, days, reason)
    if (data.detail) { setError(_detail(data)); return }
    fetchUsers()
  }
  // 重置密码（2026-10-30）：新密码由管理员输入，成功后旧会话全部失效
  const handleResetPw = async (userId: number, password: string) => {
    setError('')
    const res = await fetch(`${API_BASE}/admin/users/${userId}/reset-password`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...headers() },
      body: JSON.stringify({ password }),
    })
    const data = await res.json()
    if (!res.ok || data.detail) { setError(_detail(data) || '重置失败'); return false }
    setNotice(data.message || '密码已重置')
    return true
  }
  // 收款子页面（2026-10-30 逐笔记账）：点击「累计收款」弹窗登记/查看/删除
  const [payUser, setPayUser] = useState<null | { id: number; username: string }>(null)
  const [payments, setPayments] = useState<any[]>([])
  const [payAmt, setPayAmt] = useState('')
  const [payNote, setPayNote] = useState('')
  const [payBusy, setPayBusy] = useState(false)
  const [payMsg, setPayMsg] = useState('')

  const loadPayments = async (userId: number) => {
    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}/payments`, { headers: headers() })
      if (res.ok) setPayments(await res.json())
    } catch { /* 忽略 */ }
  }
  const openPayments = (u: { id: number; username: string }) => {
    setPayUser(u); setPayments([]); setPayAmt(''); setPayNote(''); setPayMsg('')
    loadPayments(u.id)
  }
  const handleAddPayment = async () => {
    if (!payUser) return
    const v = Number(payAmt)
    if (!(v > 0)) { setPayMsg('请输入大于 0 的金额'); return }
    setPayBusy(true); setPayMsg('')
    const res = await fetch(`${API_BASE}/admin/users/${payUser.id}/payments`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...headers() },
      body: JSON.stringify({ amount: v, note: payNote }),
    })
    const data = await res.json()
    setPayBusy(false)
    if (!res.ok || data.detail) { setPayMsg(_detail(data) || '登记失败'); return }
    setPayAmt(''); setPayNote('')
    loadPayments(payUser.id)
    fetchUsers()  // 刷新列表里的累计收款
  }
  const handleDeletePayment = async (pid: number) => {
    if (!payUser) return
    if (!window.confirm('确定删除这笔收款记录？该操作不可恢复。')) return
    const res = await fetch(`${API_BASE}/admin/users/${payUser.id}/payments/${pid}`, { method: 'DELETE', headers: headers() })
    if (res.ok) { loadPayments(payUser.id); fetchUsers() }
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
    // 与登录校验同口径（2026-10-30）：短密码/短用户名创建的账号永远无法登录
    if (newUsername.trim().length < 3) { setError('用户名至少 3 个字符'); return }
    if (newPassword.length < 8) { setError('密码至少 8 个字符'); return }
    if (newPassword !== newPassword2) { setError('两次输入的密码不一致'); return }
    setError('')
    try {
      const res = await fetch(`${API_BASE}/admin/users/create`, { method: 'POST', headers: headers(), body: JSON.stringify({ username: newUsername, password: newPassword, role: newRole }) })
      const data = await res.json()
      // 2026-10-19 修复：后端 400 返回 detail 而非 error——此前失败也清空表单
      if (!res.ok || data.error) { setError(_detail(data) || '创建失败'); return }
      setShowCreate(false); setNewUsername(''); setNewPassword(''); setNewPassword2(''); setShowPw(false)
      fetchUsers()
    } catch { setError('创建失败') }
  }

  return (
    <>
      {error && <ErrorMsg msg={error} onRetry={fetchUsers} />}
      {notice && !error && (
        <div style={{ fontSize: 13, padding: '10px 14px', background: 'var(--success-soft)', color: 'var(--success)', borderRadius: 8, marginBottom: 12 }}>
          {notice}
          <button onClick={() => setNotice('')} title="关闭" aria-label="关闭" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--success)', float: 'right', padding: 0, lineHeight: 1.6, display: 'flex' }}><XIcon size={14} /></button>
        </div>
      )}
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        {!showCreate ? <button onClick={() => setShowCreate(true)} title="创建用户" aria-label="创建用户" style={btnPrimary}>+ 创建用户</button> : (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} placeholder="用户名（≥3 位，任意字符）" style={{ ...inputStyle, width: 140 }} />
            {/* 密码输入 — 带小眼睛明文切换；≥8 位与登录校验同口径 */}
            <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
              <input value={newPassword} onChange={(e) => setNewPassword(e.target.value)} type={showPw ? 'text' : 'password'} placeholder="密码（≥8 位，任意字符）" style={{ ...inputStyle, width: 130, paddingRight: 32 }} />
              <button onClick={() => setShowPw(!showPw)} title={showPw ? '隐藏密码' : '显示密码'}
                style={{ position: 'absolute', right: 6, background: 'none', border: 'none', cursor: 'pointer', padding: 2, color: 'var(--text-muted)', display: 'flex', lineHeight: 1 }}>
                {showPw ? (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                    <line x1="1" y1="1" x2="23" y2="23"/>
                  </svg>
                ) : (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                  </svg>
                )}
              </button>
            </div>
            {/* 确认密码 — 与小眼睛共用明文切换 */}
            <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
              <input value={newPassword2} onChange={(e) => setNewPassword2(e.target.value)} type={showPw ? 'text' : 'password'} placeholder="确认密码" style={{ ...inputStyle, width: 130, paddingRight: 32, borderColor: newPassword2 && newPassword2 !== newPassword ? 'var(--danger)' : undefined }} />
              <button onClick={() => setShowPw(!showPw)} title={showPw ? '隐藏密码' : '显示密码'}
                style={{ position: 'absolute', right: 6, background: 'none', border: 'none', cursor: 'pointer', padding: 2, color: 'var(--text-muted)', display: 'flex', lineHeight: 1 }}>
                {showPw ? (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                    <line x1="1" y1="1" x2="23" y2="23"/>
                  </svg>
                ) : (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                  </svg>
                )}
              </button>
            </div>
            <select value={newRole} onChange={(e) => setNewRole(e.target.value)} style={{ padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)' }}>
              <option value="user">user</option><option value="admin">admin</option>
            </select>
            <button onClick={handleCreateUser} title="确定" aria-label="确定" style={btnPrimary}>确定</button>
            <button onClick={() => { setShowCreate(false); setNewPassword2(''); setShowPw(false) }} title="取消" aria-label="取消" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--text-muted)' }}>取消</button>
          </div>
        )}
        <div style={{ flex: 1 }} />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜索用户名或 ID..." style={{ ...inputStyle, width: 200 }} />
      </div>
      {loading ? <Spinner /> : (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: 'var(--bg-tertiary)' }}>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, borderBottom: '2px solid var(--border)' }}>ID</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, borderBottom: '2px solid var(--border)' }}>昵称</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, borderBottom: '2px solid var(--border)' }}>账号</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, borderBottom: '2px solid var(--border)' }}>邮箱</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, borderBottom: '2px solid var(--border)' }}>角色</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, borderBottom: '2px solid var(--border)' }}>状态</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, borderBottom: '2px solid var(--border)' }}>注册时间</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, borderBottom: '2px solid var(--border)' }}
                title="显示金额 = 收款 − 系数成本（实际成本×盈利系数）；负=欠费，正=余额；副行为换算过程">显示金额(¥)</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, borderBottom: '2px solid var(--border)' }}>收款(¥)</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, borderBottom: '2px solid var(--border)' }}>操作</th>
            </tr></thead>
            <tbody>
              {filtered.length === 0 && <tr><td colSpan={10}><Empty msg={search ? '无匹配用户' : '暂无用户'} /></td></tr>}
              {filtered.map((u) => {
                const isAdminRole = u.role === 'admin'; const isFrozen = u.frozen
                return (
                  <tr key={u.id} style={{ borderBottom: '1px solid var(--border-light)', opacity: isFrozen ? 0.5 : 1 }}>
                    <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontSize: 12 }}>{u.id}</td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-primary)', fontWeight: 600 }}>{u.display_name || '—'}{isAdminRole && badge('管理员', 'var(--accent)')}{isFrozen && badge('已冻结', 'var(--danger)')}</td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-secondary)', fontSize: 12.5 }}>{u.username}</td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-secondary)', fontSize: 12.5 }}>{u.email || '—'}</td>
                    <td style={{ padding: '10px 14px' }}>{isAdminRole ? <span style={{ color: 'var(--accent)', fontWeight: 600 }}>admin</span> : <span style={{ color: 'var(--text-secondary)' }}>user</span>}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--text-muted)' }}
                      title={isFrozen && u.freeze_reason ? `冻结原因：${u.freeze_reason}` : undefined}>
                      {isFrozen ? `冻结至 ${u.frozen_until?.slice(0, 10)}` : '正常'}
                    </td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontSize: 12 }}>{u.create_time?.slice(0, 10)}</td>
                    {/* 财务口径（2026-10-30）：显示金额 = 收款 − 系数成本（负=欠费，正=余额）；
                        副行展示换算：实际成本(4位) × 系数 = 系数成本 */}
                    <td style={{ padding: '10px 14px' }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: (u.paid - u.billed) < 0 ? 'var(--danger)' : 'var(--success)' }}>
                        {fmtCostSigned(u.paid - u.billed)}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        实际成本 {fmtCostNeg4(u.cost)} → 系数成本 {fmtCostNeg4(u.billed)}
                      </div>
                    </td>
                    <td style={{ padding: '10px 14px', fontSize: 12, fontWeight: 600, color: 'var(--success)' }}>
                      {!isAdminRole ? (
                        <button onClick={() => openPayments({ id: u.id, username: u.username })}
                          title="累计收款（点击查看/登记每笔收款）" aria-label="累计收款"
                          style={{ fontSize: 12, padding: '2px 8px', color: 'var(--success)', border: '1px solid var(--success)', background: 'none', borderRadius: 4, cursor: 'pointer' }}>
                          ¥{fmtCost(u.paid)}
                        </button>
                      ) : '—'}
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      {!isAdminRole && <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
                        {isFrozen ? <button onClick={() => handleFreeze(u.id, 0)} title="解冻" aria-label="解冻" style={{ fontSize: 12, padding: '4px 10px', color: 'var(--success)', border: '1px solid var(--success)', background: 'none', borderRadius: 4, cursor: 'pointer' }}>解冻</button> : <FreezeBtn userId={u.id} onFreeze={handleFreeze} />}
                        {/* 重置密码（2026-10-30）：bcrypt 单向哈希无法显示原密码，管理员直接设新密码 */}
                        <ResetPwBtn userId={u.id} onReset={handleResetPw} />
                        <button onClick={() => handleDeleteUser(u.id, u.username)} title="删除" aria-label="删除" style={btnDangerSm}>删除</button>
                      </div>}
                    </td>
                  </tr>)
              })}
            </tbody>
          </table>
        </Card>
      )}

      {/* 收款子页面（2026-10-30 逐笔记账）：累计收款 + 每笔记录 + 登记/删除 */}
      {payUser && (
        <Modal open title={`收款记录 — ${payUser.username}`} onClose={() => setPayUser(null)} width={520}>
          <div style={{ minWidth: 420 }}>
            {/* 登记新收款 */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 14, alignItems: 'center', flexWrap: 'wrap' }}>
              <input value={payAmt} onChange={(e) => setPayAmt(e.target.value)} type="number" min={0} step={0.01}
                placeholder="金额（元）" style={{ ...inputStyle, width: 110 }} />
              <input value={payNote} onChange={(e) => setPayNote(e.target.value)} maxLength={200}
                placeholder="备注（选填，如支付方式/月份）" style={{ ...inputStyle, width: 170, flex: 1 }} />
              <button onClick={handleAddPayment} disabled={payBusy}
                style={{ ...btnPrimary, opacity: payBusy ? 0.6 : 1 }}>登记收款</button>
            </div>
            {payMsg && <div style={{ fontSize: 12, color: 'var(--danger)', marginBottom: 10 }}>{payMsg}</div>}
            {/* 累计 */}
            <div style={{ fontSize: 13, color: 'var(--text-primary)', marginBottom: 10 }}>
              累计收款：<b style={{ color: 'var(--success)' }}>
                ¥{fmtCost(payments.reduce((s, p) => s + (Number(p.amount) || 0), 0))}
              </b>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 6 }}>共 {payments.length} 笔</span>
            </div>
            {/* 记录列表 */}
            <div style={{ maxHeight: 260, overflowY: 'auto', border: '1px solid var(--border-light)', borderRadius: 8 }}>
              {payments.length === 0 ? (
                <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>暂无收款记录</div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <tbody>
                    {payments.map((p) => (
                      <tr key={p.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                        <td style={{ padding: '8px 12px', color: 'var(--text-muted)', fontSize: 11, whiteSpace: 'nowrap' }}>{p.created_at?.slice(0, 16)}</td>
                        <td style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--success)' }}>¥{fmtCost(p.amount)}</td>
                        <td style={{ padding: '8px 12px', color: 'var(--text-secondary)', fontSize: 11 }}>{p.note || '—'}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                          <button onClick={() => handleDeletePayment(p.id)} title="删除" aria-label="删除"
                            style={{ fontSize: 11, padding: '2px 8px', color: 'var(--danger)', border: '1px solid var(--danger)', background: 'none', borderRadius: 4, cursor: 'pointer' }}>删除</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}

/* 重置密码（2026-10-30）：密码 bcrypt 单向哈希无法反解，管理员直接设新密码 */
function ResetPwBtn({ userId, onReset }: { userId: number; onReset: (id: number, password: string) => Promise<boolean> }) {
  const [open, setOpen] = useState(false); const [pw, setPw] = useState(''); const [busy, setBusy] = useState(false)
  if (!open) return <button onClick={() => setOpen(true)} title="重置密码" aria-label="重置密码" style={{ fontSize: 12, padding: '4px 10px', color: 'var(--accent)', border: '1px solid var(--accent)', background: 'none', borderRadius: 4, cursor: 'pointer' }}>重置密码</button>
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
      <input value={pw} onChange={(e) => setPw(e.target.value)} placeholder="新密码（≥8 位，任意字符）" style={{ width: 150, padding: '4px 6px', borderRadius: 4, border: '1px solid var(--border)', fontSize: 12, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)' }} />
      <button onClick={async () => {
        if (pw.length < 8) return
        setBusy(true)
        const ok = await onReset(userId, pw)
        setBusy(false)
        if (ok) { setOpen(false); setPw('') }
      }} disabled={pw.length < 8 || busy} title="确定" aria-label="确定"
        style={{ fontSize: 11, padding: '4px 8px', color: '#fff', background: 'var(--accent)', border: 'none', borderRadius: 4, cursor: pw.length >= 8 && !busy ? 'pointer' : 'default', opacity: pw.length >= 8 && !busy ? 1 : 0.55 }}>确定</button>
      <button onClick={() => setOpen(false)} title="关闭" aria-label="关闭" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '2px 4px', display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1 }}><XIcon size={13} /></button>
    </div>
  )
}

function FreezeBtn({ userId, onFreeze }: { userId: number; onFreeze: (id: number, days: number, reason: string) => void }) {
  const [open, setOpen] = useState(false); const [days, setDays] = useState(7)
  const [reason, setReason] = useState('')
  if (!open) return <button onClick={() => setOpen(true)} title="冻结" aria-label="冻结" style={{ fontSize: 12, padding: '4px 10px', color: 'var(--danger)', border: '1px solid var(--danger)', background: 'none', borderRadius: 4, cursor: 'pointer' }}>冻结</button>
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
      <input type="number" min={1} max={365} value={days} onChange={(e) => setDays(Number(e.target.value))} style={{ width: 48, padding: '4px 6px', borderRadius: 4, border: '1px solid var(--border)', fontSize: 12, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)' }} />
      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>天</span>
      {/* C7（2026-10-29）：冻结原因，登录时向用户展示 */}
      <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="冻结原因（选填，展示给用户）" style={{ width: 150, padding: '4px 6px', borderRadius: 4, border: '1px solid var(--border)', fontSize: 12, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)' }} />
      <button onClick={() => { onFreeze(userId, days, reason); setOpen(false); setReason('') }} title="确定" aria-label="确定" style={{ fontSize: 11, padding: '4px 8px', color: '#fff', background: 'var(--danger)', border: 'none', borderRadius: 4, cursor: 'pointer' }}>确定</button>
      <button onClick={() => setOpen(false)} title="关闭" aria-label="关闭" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '2px 4px', display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1 }}><XIcon size={13} /></button>
    </div>
  )
}
