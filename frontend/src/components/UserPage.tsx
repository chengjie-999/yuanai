import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { updateProfile, changePassword, deleteAccount } from '../api'
import { useIsMobile } from '../hooks/useIsMobile'
import Modal from './Modal'

const C = {
  card: { background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' } as const,
  title: { fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', padding: '16px 20px', borderBottom: '1px solid var(--border-light)' } as const,
  sub: { fontSize: 11, color: 'var(--text-muted)', fontWeight: 400 } as const,
  row: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: '1px solid var(--border-light)', gap: 16 } as const,
  label: { fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 } as const,
  hint: { fontSize: 11, color: 'var(--text-muted)', marginTop: 2 } as const,
  input: { padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)' } as const,
  btn: { padding: '8px 18px', borderRadius: 6, border: 'none', background: 'var(--accent)', color: '#fff', fontSize: 13, fontWeight: 500, cursor: 'pointer' } as const,
  btnDanger: { padding: '8px 18px', borderRadius: 6, border: '1px solid var(--danger)', background: 'transparent', color: 'var(--danger)', fontSize: 13, cursor: 'pointer' } as const,
}

export default function UserPage({ user, onLogout }: { user: any; onLogout: () => void }) {
  const isMobile = useIsMobile()
  const { refresh } = useAuth()
  // C4 注销（2026-10-29）：密码确认 → 级联删除全部数据 → 退出
  const [deleting, setDeleting] = useState(false)
  const handleDeleteAccount = async () => {
    const pwd = window.prompt('此操作将永久删除你的全部数据（会话/记忆/数据集/知识星球等），不可恢复。' +
      '请输入密码确认：')
    if (!pwd) return
    if (!window.confirm('再次确认：删除后所有数据将无法找回，确定注销账号？')) return
    setDeleting(true)
    try {
      const ok = await deleteAccount(pwd)
      if (ok) {
        window.alert('账号已注销，所有数据已删除。')
        onLogout()
      } else {
        window.alert('注销失败，请重试（密码是否正确？）')
      }
    } finally {
      setDeleting(false)
    }
  }
  const [name, setName] = useState(user?.display_name || '')
  const [nameMsg, setNameMsg] = useState('')
  // password flow
  const [showPw, setShowPw] = useState(false)
  const [pwStep, setPwStep] = useState(0) // 0=old, 1=new+confirm, 2=done
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [pwMsg, setPwMsg] = useState('')
  const [pwErr, setPwErr] = useState(false)

  const handleSaveName = async () => {
    if (!name.trim()) return
    try {
      await updateProfile(name.trim())
      setNameMsg('已保存')
      refresh()
      setTimeout(() => setNameMsg(''), 2000)
    } catch (e: any) { setNameMsg(e.message || '保存失败') }
  }

  const resetPw = () => { setShowPw(false); setPwStep(0); setOldPw(''); setNewPw(''); setConfirmPw(''); setPwMsg(''); setPwErr(false) }

  const handlePwNext = () => {
    setPwErr(false); setPwMsg('')
    if (!oldPw) { setPwMsg('请输入原密码'); setPwErr(true); return }
    setPwStep(1)
  }

  const handlePwSubmit = async () => {
    setPwErr(false); setPwMsg('')
    if (!newPw) { setPwMsg('请输入新密码'); setPwErr(true); return }
    if (newPw.length < 8) { setPwMsg('新密码至少 8 个字符'); setPwErr(true); return }
    if (newPw !== confirmPw) { setPwMsg('两次输入的密码不一致'); setPwErr(true); return }
    try {
      await changePassword(oldPw, newPw)
      setPwStep(2)
    } catch (e: any) { setPwMsg(e.message || '修改失败'); setPwErr(true) }
  }

  return (
    <div style={{ height: '100%', overflow: 'auto', background: 'var(--bg-secondary)', padding: isMobile ? '20px 14px' : '40px 20px', display: 'flex', justifyContent: 'center' }}>
      <div style={{ maxWidth: 480, width: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* ---- 个人信息 ---- */}
        <div style={C.card}>
          <div style={{ padding: '32px', textAlign: 'center', borderBottom: '1px solid var(--border-light)' }}>
            <div style={{
              width: 64, height: 64, borderRadius: '50%', background: 'var(--accent)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              margin: '0 auto 12px', color: '#fff', fontSize: 24, fontWeight: 700,
            }}>
              {(user?.username || 'U')[0].toUpperCase()}
            </div>
            <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 4px' }}>{user?.display_name || user?.username}</h2>
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>@{user?.username}</span>
          </div>
          <div style={C.row}>
            <div>
              <div style={C.label}>用户 ID</div>
            </div>
            <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontFamily: 'monospace' }}>{user?.id}</span>
          </div>
          <div style={C.row}>
            <div>
              <div style={C.label}>角色</div>
            </div>
            <span style={{
              fontSize: 12, fontWeight: 500, padding: '2px 10px', borderRadius: 4,
              background: user?.role === 'admin' ? 'var(--accent-light)' : 'var(--bg-tertiary)',
              color: user?.role === 'admin' ? 'var(--accent)' : 'var(--text-secondary)',
            }}>{user?.role === 'admin' ? '管理员' : '普通用户'}</span>
          </div>
          <div style={C.row}>
            <div style={{ flex: 1 }}>
              <div style={C.label}>显示名称</div>
              <div style={C.hint}>对话中显示的名称</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input value={name} onChange={e => setName(e.target.value)} style={{ ...C.input, width: 140 }} placeholder={user?.username} />
              <button onClick={handleSaveName} style={{ ...C.btn, fontSize: 12, padding: '6px 14px' }}>保存</button>
            </div>
          </div>
          {nameMsg && (
            <div style={{ padding: '0 20px 14px', fontSize: 12, color: 'var(--success)' }}>{nameMsg}</div>
          )}
          <div style={C.row}>
            <div>
              <div style={C.label}>本机 Agent</div>
              <div style={C.hint}>旧命令 --agent-id 已淘汰——安装请到「Agent 页」顶部下载安装包并粘贴安装码（自动绑定本账号）；终端（开发者）用 <code style={{ fontSize: 11 }}>yuan --install &lt;安装码&gt;</code></div>
            </div>
          </div>
        </div>

        {/* ---- 修改密码 ---- */}
        <button onClick={() => setShowPw(true)} style={{
          width: '100%', padding: '12px 0', borderRadius: 10,
          border: '1px solid var(--border)', background: 'var(--bg-primary)',
          cursor: 'pointer', fontSize: 14, color: 'var(--text-secondary)',
        }}>修改密码</button>

        {/* ---- 退出 ---- */}
        <button onClick={onLogout} style={{
          width: '100%', padding: '12px 0', borderRadius: 10,
          border: '1px solid var(--border)', background: 'var(--bg-primary)',
          cursor: 'pointer', fontSize: 14, color: 'var(--danger)',
        }}>退出登录</button>

        {/* ---- 注销账号（C4 合规 2026-10-29：降级为不显眼的小字入口——密码确认 + 级联删除，不可恢复） ---- */}
        <div style={{ textAlign: 'center', marginTop: 8 }}>
          <button onClick={handleDeleteAccount} disabled={deleting}
            style={{ background: 'none', border: 'none', cursor: deleting ? 'default' : 'pointer',
              fontSize: 12, color: 'var(--text-muted)', textDecoration: 'underline',
              opacity: deleting ? 0.6 : 1 }}
            onMouseEnter={(e) => { if (!deleting) e.currentTarget.style.color = 'var(--danger)' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}>
            {deleting ? '注销中…' : '注销账号'}
          </button>
        </div>
      </div>

      {/* ---- 修改密码侧边抽屉（共享 Modal mode=right） ---- */}
      <Modal open={showPw} mode="right" onClose={resetPw}
        title={pwStep === 2 ? '修改完成' : pwStep === 1 ? '设置新密码' : '修改密码'}
        footer={pwStep !== 2 ? (
          <>
            <button onClick={pwStep === 0 ? resetPw : () => { setPwStep(0); setPwMsg('') }}
              style={{ padding: '10px 24px', borderRadius: 6, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', fontSize: 14, cursor: 'pointer' }}>
              {pwStep === 0 ? '取消' : '上一步'}
            </button>
            <button onClick={pwStep === 0 ? handlePwNext : handlePwSubmit}
              style={{ ...C.btn, fontSize: 14, padding: '10px 24px' }}>
              {pwStep === 0 ? '下一步' : '确认修改'}
            </button>
          </>
        ) : (
          <button onClick={onLogout} style={{ ...C.btn, fontSize: 14, padding: '10px 32px' }}>重新登录</button>
        )}>
        {pwStep === 0 && (
          <div>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '0 0 20px' }}>为确保账号安全，请先验证原密码</p>
            <div style={{ marginBottom: 20 }}>
              <div style={{ ...C.label, marginBottom: 6, fontSize: 14 }}>原密码</div>
              <input type="password" value={oldPw} onChange={e => setOldPw(e.target.value)}
                style={{ ...C.input, width: '100%', fontSize: 14, padding: '10px 14px' }}
                placeholder="输入当前密码" autoFocus
                onKeyDown={e => e.key === 'Enter' && handlePwNext()} />
            </div>
            {pwMsg && <div style={{ fontSize: 13, color: pwErr ? 'var(--danger)' : 'var(--success)', marginBottom: 16, padding: '8px 12px', borderRadius: 6, background: pwErr ? 'rgba(244,71,71,0.08)' : 'rgba(106,153,85,0.08)' }}>{pwMsg}</div>}
          </div>
        )}
        {pwStep === 1 && (
          <div>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '0 0 20px' }}>请输入新密码：至少 8 位，任意字符均可（中文/字母/数字/符号）</p>
            <div style={{ marginBottom: 16 }}>
              <div style={{ ...C.label, marginBottom: 6, fontSize: 14 }}>新密码</div>
              <input type="password" value={newPw} onChange={e => setNewPw(e.target.value)}
                style={{ ...C.input, width: '100%', fontSize: 14, padding: '10px 14px' }}
                placeholder="至少 8 位，任意字符" autoFocus />
            </div>
            <div style={{ marginBottom: 20 }}>
              <div style={{ ...C.label, marginBottom: 6, fontSize: 14 }}>确认新密码</div>
              <input type="password" value={confirmPw} onChange={e => setConfirmPw(e.target.value)}
                style={{ ...C.input, width: '100%', fontSize: 14, padding: '10px 14px' }}
                placeholder="再次输入新密码"
                onKeyDown={e => e.key === 'Enter' && handlePwSubmit()} />
            </div>
            {pwMsg && <div style={{ fontSize: 13, color: pwErr ? 'var(--danger)' : 'var(--success)', marginBottom: 16, padding: '8px 12px', borderRadius: 6, background: pwErr ? 'rgba(244,71,71,0.08)' : 'rgba(106,153,85,0.08)' }}>{pwMsg}</div>}
          </div>
        )}
        {pwStep === 2 && (
          <div style={{ textAlign: 'center', paddingTop: 20 }}>
            <div style={{ marginBottom: 12, color: 'var(--success)' }}>
              <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
            </div>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>密码修改成功</div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20 }}>
              为安全起见，改密后所有旧登录已失效——请使用新密码重新登录。
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
