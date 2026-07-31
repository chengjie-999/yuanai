import { useState, useEffect, useRef } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { login } from '../api'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'

export default function LoginPage() {
  const { login: handleLogin, token } = useAuth()
  const { theme, setTheme } = useTheme()
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [remember, setRemember] = useState(true)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [entering, setEntering] = useState(true)

  const userRef = useRef<HTMLInputElement>(null)

  // 入场动画
  useEffect(() => {
    requestAnimationFrame(() => setEntering(false))
    userRef.current?.focus()
  }, [])

  // 从 sessionStorage 读取被踢出/锁定的提示
  useEffect(() => {
    const msg = sessionStorage.getItem('loginError')
    if (msg) {
      setError(msg)
      sessionStorage.removeItem('loginError')
    }
  }, [])

  const handleSubmit = async () => {
    const trimmedUser = username.trim()
    if (!trimmedUser || !password) {
      setError('请填写用户名和密码')
      return
    }
    if (password.length < 8) {
      setError('密码至少 8 个字符')
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await login(trimmedUser, password)
      if (!data?.token) {
        setError('登录失败，服务器返回异常')
        setLoading(false)
        return
      }
      handleLogin(data.token, data.user, remember)
      if (data.user?.theme && data.user.theme !== theme) {
        setTheme(data.user.theme)
      }
      navigate('/', { replace: true })
    } catch (e: any) {
      setError(e.message || '操作失败')
    }
    setLoading(false)
  }

  if (token) return <Navigate to="/" replace />

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg-secondary)',
      padding: '16px',
      transition: 'opacity 0.4s ease, transform 0.4s ease',
      opacity: entering ? 0 : 1,
      transform: entering ? 'translateY(10px)' : 'translateY(0)',
    }}>
      <div style={{
        width: '100%',
        maxWidth: 420,
        padding: '40px 32px',
        background: 'var(--bg-primary)',
        borderRadius: 16,
        boxShadow: '0 4px 24px var(--shadow-md)',
      }}>
        {/* ======== Header ======== */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 14,
            background: 'var(--accent)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 16,
            fontSize: 28,
            color: '#fff',
            fontWeight: 700,
          }}>
            Y
          </div>
          <h1 style={{
            fontSize: 22, fontWeight: 700, margin: 0, marginBottom: 6,
            color: 'var(--text-primary)',
          }}>
            欢迎回到小元AI
          </h1>
          <p style={{
            fontSize: 14, color: 'var(--text-secondary)', margin: 0,
          }}>
            请输入账号密码以继续
          </p>
        </div>

        {/* ======== Error ======== */}
        {error && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 14px', borderRadius: 8,
            background: 'var(--danger)', color: '#fff',
            fontSize: 13, marginBottom: 20,
            animation: 'shake 0.4s ease',
          }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <circle cx="12" cy="12" r="10"/>
              <line x1="15" y1="9" x2="9" y2="15"/>
              <line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
            <span style={{ flex: 1 }}>{error}</span>
            <button onClick={() => setError('')} style={{
              background: 'none', border: 'none', color: '#fff', cursor: 'pointer',
              fontSize: 16, padding: '0 4px', lineHeight: 1, opacity: 0.8,
            }}>×</button>
          </div>
        )}

        {/* ======== Username ======== */}
        <div style={{ marginBottom: 14 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 0,
            border: '1.5px solid var(--border)',
            borderRadius: 10,
            background: 'var(--bg-input, var(--bg-primary))',
            transition: 'border-color 0.2s, box-shadow 0.2s',
            overflow: 'hidden',
          }}
            onFocus={(e) => {
              const el = e.currentTarget
              el.style.borderColor = 'var(--accent)'
              el.style.boxShadow = '0 0 0 3px var(--accent-light)'
            }}
            onBlur={(e) => {
              const el = e.currentTarget
              el.style.borderColor = 'var(--border)'
              el.style.boxShadow = 'none'
            }}
          >
            <span style={{
              padding: '12px 0 12px 14px',
              color: 'var(--text-muted)',
              display: 'flex',
            }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
            </span>
            <input
              ref={userRef}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              placeholder="用户名"
              autoComplete="username"
              style={{
                width: '100%', padding: '12px 14px 12px 8px', border: 'none', fontSize: 15,
                outline: 'none', background: 'transparent', color: 'var(--text-primary)',
              }}
            />
          </div>
        </div>

        {/* ======== Password ======== */}
        <div style={{ marginBottom: 14 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 0,
            border: '1.5px solid var(--border)',
            borderRadius: 10,
            background: 'var(--bg-input, var(--bg-primary))',
            transition: 'border-color 0.2s, box-shadow 0.2s',
            overflow: 'hidden',
          }}
            onFocus={(e) => {
              const el = e.currentTarget
              el.style.borderColor = 'var(--accent)'
              el.style.boxShadow = '0 0 0 3px var(--accent-light)'
            }}
            onBlur={(e) => {
              const el = e.currentTarget
              el.style.borderColor = 'var(--border)'
              el.style.boxShadow = 'none'
            }}
          >
            <span style={{
              padding: '12px 0 12px 14px',
              color: 'var(--text-muted)',
              display: 'flex',
            }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
            </span>
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              type={showPw ? 'text' : 'password'}
              placeholder="密码"
              autoComplete="current-password"
              style={{
                width: '100%', padding: '12px 8px', border: 'none', fontSize: 15,
                outline: 'none', background: 'transparent', color: 'var(--text-primary)',
              }}
            />
            <button
              type="button"
              onClick={() => setShowPw(!showPw)}
              tabIndex={-1}
              style={{
                padding: '12px 14px 12px 0', background: 'none', border: 'none',
                cursor: 'pointer', color: 'var(--text-muted)', display: 'flex',
                opacity: 0.6, transition: 'opacity 0.15s',
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = '1' }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = '0.6' }}
            >
              {showPw ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                  <path d="m14.12 14.12a3 3 0 1 1-4.24-4.24"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* ======== 记住我 ======== */}
        <label style={{
          display: 'flex', alignItems: 'center', gap: 8,
          cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)',
          marginBottom: 24, userSelect: 'none',
        }}>
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
            style={{
              width: 16, height: 16, accentColor: 'var(--accent)',
              cursor: 'pointer',
            }}
          />
          记住我（关闭浏览器后保持登录）
        </label>

        {/* ======== Submit ======== */}
        <button
          onClick={handleSubmit}
          disabled={loading}
          style={{
            width: '100%',
            padding: '13px 0',
            borderRadius: 10,
            border: 'none',
            background: loading ? 'var(--text-muted)' : 'var(--accent)',
            color: '#fff',
            fontSize: 15,
            fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'background 0.2s, transform 0.1s, box-shadow 0.2s',
            boxShadow: loading ? 'none' : '0 2px 8px rgba(25,118,210,0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
          }}
          onMouseEnter={(e) => {
            if (!loading) {
              (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 14px rgba(25,118,210,0.4)'
            }
          }}
          onMouseLeave={(e) => {
            if (!loading) {
              (e.currentTarget as HTMLElement).style.boxShadow = '0 2px 8px rgba(25,118,210,0.3)'
            }
          }}
          onMouseDown={(e) => {
            if (!loading) {
              (e.currentTarget as HTMLElement).style.transform = 'scale(0.98)'
            }
          }}
          onMouseUp={(e) => {
            (e.currentTarget as HTMLElement).style.transform = 'scale(1)'
          }}
        >
          {loading ? (
            <>
              <span style={{
                width: 16, height: 16, border: '2px solid rgba(255,255,255,0.3)',
                borderTopColor: '#fff', borderRadius: '50%',
                animation: 'spin 0.6s linear infinite',
              }}/>
              登录中...
            </>
          ) : '登  录'}
        </button>
      </div>

      {/* ======== CSS keyframes ======== */}
      <style>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          20% { transform: translateX(-6px); }
          40% { transform: translateX(6px); }
          60% { transform: translateX(-4px); }
          80% { transform: translateX(4px); }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
