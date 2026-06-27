import { useState, useEffect } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { login, register } from '../api'
import { useAuth } from '../contexts/AuthContext'

export default function LoginPage() {
  const { login: handleLogin, token } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [password2, setPassword2] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const msg = sessionStorage.getItem('loginError')
    if (msg) {
      setError(msg)
      sessionStorage.removeItem('loginError')
    }
  }, [])

  const handleSubmit = async () => {
    if (!username.trim() || !password.trim()) { setError('请填写用户名和密码'); return }
    if (tab === 'register' && password !== password2) { setError('两次密码输入不一致'); return }
    setLoading(true)
    setError('')
    try {
      const data = tab === 'login' ? await login(username, password) : await register(username, password)
      if (!data?.token) { setError('登录失败，服务器返回异常'); setLoading(false); return }
      handleLogin(data.token, data.user)
      navigate('/', { replace: true })
    } catch (e: any) {
      setError(e.message || '操作失败')
    }
    setLoading(false)
  }

  if (token) return <Navigate to="/" replace />

  return (
    <div style={{
      height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: '#f5f5f5',
    }}>
      <div style={{
        width: 400, padding: '40px 32px', background: '#fff', borderRadius: 12,
        boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
      }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, textAlign: 'center', marginBottom: 8, color: '#333' }}>小元AI</h1>
        <p style={{ fontSize: 14, color: '#999', textAlign: 'center', marginBottom: 28 }}>登录以继续使用</p>

        {/* Tab */}
        <div style={{ display: 'flex', marginBottom: 20, borderRadius: 8, overflow: 'hidden', border: '1px solid #ddd' }}>
          <div onClick={() => { setTab('login'); setError('') }}
            style={{ flex: 1, padding: '10px 0', textAlign: 'center', cursor: 'pointer', fontSize: 14,
              background: tab === 'login' ? '#1976d2' : '#fff', color: tab === 'login' ? '#fff' : '#666', fontWeight: tab === 'login' ? 600 : 400 }}>
            登录
          </div>
          <div onClick={() => { setTab('register'); setError('') }}
            style={{ flex: 1, padding: '10px 0', textAlign: 'center', cursor: 'pointer', fontSize: 14,
              background: tab === 'register' ? '#1976d2' : '#fff', color: tab === 'register' ? '#fff' : '#666', fontWeight: tab === 'register' ? 600 : 400 }}>
            注册
          </div>
        </div>

        {/* Form */}
        <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="用户名"
          style={{ width: '100%', padding: '12px 14px', borderRadius: 8, border: '1px solid #ddd', fontSize: 14, outline: 'none', marginBottom: 12, boxSizing: 'border-box' }} />

        <div style={{ position: 'relative', marginBottom: tab === 'register' ? 12 : 16 }}>
          <input value={password} onChange={(e) => setPassword(e.target.value)} type={showPw ? 'text' : 'password'} placeholder="密码"
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            style={{ width: '100%', padding: '12px 14px', borderRadius: 8, border: '1px solid #ddd', fontSize: 14, outline: 'none', boxSizing: 'border-box', paddingRight: 40 }} />
          <span onClick={() => setShowPw(!showPw)}
            style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', cursor: 'pointer', fontSize: 16, color: '#999', userSelect: 'none' }}>
            {showPw ? '🙈' : '👁'}
          </span>
        </div>

        {tab === 'register' && (
          <input value={password2} onChange={(e) => setPassword2(e.target.value)} type={showPw ? 'text' : 'password'} placeholder="再次输入密码"
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            style={{ width: '100%', padding: '12px 14px', borderRadius: 8, border: '1px solid #ddd', fontSize: 14, outline: 'none', marginBottom: 16, boxSizing: 'border-box' }} />
        )}

        {error && <div style={{ color: '#e53935', fontSize: 13, marginBottom: 12 }}>{error}</div>}

        <button onClick={handleSubmit} disabled={loading} className={`btn btn-primary btn-block${loading ? ' btn-loading' : ''}`}
          style={{ padding: '12px 0', fontSize: 15, fontWeight: 600 }}>
          {tab === 'login' ? '登录' : '注册'}
        </button>
      </div>
    </div>
  )
}
