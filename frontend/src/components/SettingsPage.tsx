import { useState } from 'react'
import { useTheme } from '../contexts/ThemeContext'
import { useAuth } from '../contexts/AuthContext'
import ModelSelector from './ModelSelector'
import { getStoredModel, setStoredModel } from '../api'
import { updateProfile, changePassword } from '../api'

const C = {
  card: { background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' } as const,
  title: { fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', padding: '16px 20px', borderBottom: '1px solid var(--border-light)' } as const,
  row: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: '1px solid var(--border-light)', gap: 16 } as const,
  label: { fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 } as const,
  hint: { fontSize: 11, color: 'var(--text-muted)', marginTop: 2 } as const,
  input: { padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)' } as const,
  btn: { padding: '8px 18px', borderRadius: 6, border: 'none', background: 'var(--accent)', color: '#fff', fontSize: 13, fontWeight: 500, cursor: 'pointer' } as const,
  btnOutline: { padding: '8px 18px', borderRadius: 6, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', fontSize: 13, cursor: 'pointer' } as const,
}

export default function SettingsPage() {
  const { isDark, toggle } = useTheme()
  const { user, refresh } = useAuth()
  const [model, setModel] = useState(getStoredModel())
  const [name, setName] = useState(user?.display_name || '')
  const [nameMsg, setNameMsg] = useState('')
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
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

  const handleChangePw = async () => {
    setPwErr(false); setPwMsg('')
    if (!oldPw || !newPw) { setPwMsg('请填写完整'); setPwErr(true); return }
    if (newPw.length < 8) { setPwMsg('新密码至少 8 个字符'); setPwErr(true); return }
    try {
      await changePassword(oldPw, newPw)
      setPwMsg('密码已修改')
      setOldPw(''); setNewPw('')
      setTimeout(() => setPwMsg(''), 2000)
    } catch (e: any) { setPwMsg(e.message || '修改失败'); setPwErr(true) }
  }

  return (
    <div style={{ height: '100%', overflow: 'auto', background: 'var(--bg-secondary)', padding: '32px 24px' }}>
      <div style={{ maxWidth: 600, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 4px' }}>设置</h1>

        {/* ---- 外观 ---- */}
        <div style={C.card}>
          <div style={C.title}>外观</div>
          <div style={C.row}>
            <div>
              <div style={C.label}>主题模式</div>
              <div style={C.hint}>{isDark ? '暗色模式' : '亮色模式'}</div>
            </div>
            <Toggle checked={isDark} onChange={toggle} />
          </div>
          <div style={C.row}>
            <div>
              <div style={C.label}>默认模型</div>
              <div style={C.hint}>新对话使用的 AI 模型</div>
            </div>
            <ModelSelector model={model} onChange={(v) => { setModel(v); setStoredModel(v) }} />
          </div>
        </div>

        {/* ---- 个人信息 ---- */}
        <div style={C.card}>
          <div style={C.title}>个人信息</div>
          <div style={C.row}>
            <div>
              <div style={C.label}>用户名</div>
              <div style={C.hint}>不可修改</div>
            </div>
            <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
              {user?.username}
            </span>
          </div>
          <div style={{ ...C.row, borderBottom: 'none' }}>
            <div>
              <div style={C.label}>显示名称</div>
              <div style={C.hint}>对话中显示的名称</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                style={{ ...C.input, width: 160 }}
                placeholder={user?.username}
              />
              <button onClick={handleSaveName} style={C.btn}>保存</button>
              {nameMsg && (
                <span style={{ fontSize: 11, color: 'var(--success)', whiteSpace: 'nowrap' }}>{nameMsg}</span>
              )}
            </div>
          </div>
        </div>

        {/* ---- 修改密码 ---- */}
        <div style={C.card}>
          <div style={C.title}>修改密码</div>
          <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <div style={{ ...C.label, marginBottom: 4 }}>原密码</div>
              <input
                type="password"
                value={oldPw}
                onChange={e => setOldPw(e.target.value)}
                style={{ ...C.input, width: '100%', maxWidth: 280 }}
                placeholder="输入原密码"
              />
            </div>
            <div>
              <div style={{ ...C.label, marginBottom: 4 }}>新密码</div>
              <input
                type="password"
                value={newPw}
                onChange={e => setNewPw(e.target.value)}
                style={{ ...C.input, width: '100%', maxWidth: 280 }}
                placeholder="至少 8 个字符"
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <button onClick={handleChangePw} style={C.btn}>修改密码</button>
              {pwMsg && (
                <span style={{ fontSize: 12, color: pwErr ? 'var(--danger)' : 'var(--success)' }}>{pwMsg}</span>
              )}
            </div>
          </div>
        </div>

        {/* ---- 关于 ---- */}
        <div style={C.card}>
          <div style={C.title}>关于</div>
          <div style={C.row}>
            <div style={C.label}>版本</div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>小元AI v2.0</div>
          </div>
          <div style={C.row}>
            <div style={C.label}>用户 ID</div>
            <span style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'monospace' }}>{user?.id}</span>
          </div>
          <div style={{ ...C.row, borderBottom: 'none' }}>
            <div style={C.label}>角色</div>
            <span style={{
              fontSize: 12, fontWeight: 500, padding: '2px 10px', borderRadius: 4,
              background: user?.role === 'admin' ? 'var(--accent-light)' : 'var(--bg-tertiary)',
              color: user?.role === 'admin' ? 'var(--accent)' : 'var(--text-secondary)',
            }}>{user?.role === 'admin' ? '管理员' : '普通用户'}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div
      onClick={() => onChange(!checked)}
      style={{
        width: 40, height: 22, borderRadius: 11,
        background: checked ? 'var(--accent)' : 'var(--text-muted)',
        cursor: 'pointer', position: 'relative',
        transition: 'background 0.2s', flexShrink: 0,
      }}
    >
      <div style={{
        width: 18, height: 18, borderRadius: '50%', background: '#fff',
        position: 'absolute', top: 2,
        left: checked ? 20 : 2,
        transition: 'left 0.2s',
        boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
      }} />
    </div>
  )
}
