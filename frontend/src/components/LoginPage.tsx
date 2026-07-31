import { useState, useEffect, useRef } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { login } from '../api'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import Mascot from './Mascot'

/* ============================================================
   小元AI 登录页 — 左右分栏布局（桌面端），移动端退化为卡片
   ============================================================ */

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
  const [visible, setVisible] = useState(false)
  const [focused, setFocused] = useState<'user' | 'pw' | null>(null)

  const userRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true))
    const t = setTimeout(() => userRef.current?.focus(), 400)
    return () => clearTimeout(t)
  }, [])

  useEffect(() => {
    const msg = sessionStorage.getItem('loginError')
    if (msg) { setError(msg); sessionStorage.removeItem('loginError') }
  }, [])

  const handleSubmit = async () => {
    const u = username.trim()
    if (!u || !password) { setError('请填写用户名和密码'); return }
    if (password.length < 8) { setError('密码至少 8 个字符'); return }
    setLoading(true)
    setError('')
    try {
      const data = await login(u, password)
      if (!data?.token) { setError('登录失败，服务器返回异常'); setLoading(false); return }
      handleLogin(data.token, data.user, remember)
      if (data.user?.theme && data.user.theme !== theme) setTheme(data.user.theme)
      navigate('/', { replace: true })
    } catch (e: any) {
      setError(e.message || '操作失败')
    }
    setLoading(false)
  }

  if (token) return <Navigate to="/" replace />

  const BrandPanel = (
    <div className="login-brand">
      {/* 装饰光晕 */}
      <div className="login-orb orb-1" />
      <div className="login-orb orb-2" />
      <div className="login-orb orb-3" />

      <div className="login-brand-content">
        <div className="login-logo">
          <Mascot size={88} />
        </div>

        <h2 className="login-brand-title">小元AI</h2>
        <p className="login-brand-desc">云边协同 · 多智能体协作平台</p>

        <div className="login-features">
          {[
            { icon: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5', label: '多模型智能对话' },
            { icon: 'M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3', label: '数据分析与可视化' },
            { icon: 'M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75', label: '多 Agent 协同工作' },
          ].map((feat, i) => (
            <div key={i} className="login-feat-item" style={{ animationDelay: `${0.5 + i * 0.12}s` }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d={feat.icon}/>
              </svg>
              <span>{feat.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )

  const FormPanel = (
    <div className="login-form-panel">
      <div className="login-form-inner">
        {/* 移动端显示的品牌标识 */}
        <div className="login-mobile-header">
          <Mascot size={56} />
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 4px' }}>欢迎回来</h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>登录小元AI账号以继续</p>
        </div>

        {/* 错误提示 */}
        <div className={`login-error ${error ? 'show' : ''}`}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          <span>{error || ''}</span>
          <button onClick={() => setError('')} className="login-error-close">×</button>
        </div>

        {/* 用户名 */}
        <div className={`login-input-wrap ${focused === 'user' ? 'focused' : ''}`}>
          <span className="login-input-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
            </svg>
          </span>
          <input
            ref={userRef}
            value={username}
            onChange={e => setUsername(e.target.value)}
            onFocus={() => setFocused('user')}
            onBlur={() => setFocused(null)}
            onKeyDown={e => e.key === 'Enter' && handleSubmit()}
            placeholder="用户名"
            autoComplete="username"
          />
        </div>

        {/* 密码 */}
        <div className={`login-input-wrap ${focused === 'pw' ? 'focused' : ''}`}>
          <span className="login-input-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
          </span>
          <input
            value={password}
            onChange={e => setPassword(e.target.value)}
            onFocus={() => setFocused('pw')}
            onBlur={() => setFocused(null)}
            onKeyDown={e => e.key === 'Enter' && handleSubmit()}
            type={showPw ? 'text' : 'password'}
            placeholder="密码"
            autoComplete="current-password"
          />
          <button type="button" className="login-eye" onClick={() => setShowPw(!showPw)} tabIndex={-1}>
            {showPw ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                <line x1="1" y1="1" x2="23" y2="23"/>
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
              </svg>
            )}
          </button>
        </div>

        {/* 记住我 */}
        <label className="login-remember">
          <span className={`login-checkbox ${remember ? 'checked' : ''}`}>
            {remember && (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            )}
          </span>
          <input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)} style={{ display: 'none' }}/>
          记住我
        </label>

        {/* 登录按钮 */}
        <button className={`login-btn ${loading ? 'loading' : ''}`} onClick={handleSubmit} disabled={loading}>
          {loading ? (
            <><span className="login-spinner"/> 登录中...</>
          ) : '登  录'}
        </button>
      </div>
    </div>
  )

  return (
    <div className={`login-page ${visible ? 'visible' : ''}`}>
      {BrandPanel}
      {FormPanel}

      <style>{`
        /* ============================
           登录页 — 全局样式
           ============================ */
        .login-page {
          min-height: 100vh;
          display: flex;
          opacity: 0;
          transition: opacity 0.5s ease;
          background: var(--bg-primary);
        }
        .login-page.visible { opacity: 1; }

        /* ============================
           左侧品牌面板
           ============================ */
        .login-brand {
          position: relative;
          flex: 0 0 46%;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, #1565c0 0%, #0d47a1 40%, #1a237e 100%);
          overflow: hidden;
          padding: 48px;
        }
        [data-theme="dark"] .login-brand {
          background: linear-gradient(135deg, #0d2137 0%, #0a1628 40%, #0f1a2e 100%);
        }

        /* 装饰光晕 */
        .login-orb {
          position: absolute;
          border-radius: 50%;
          filter: blur(80px);
          opacity: 0.3;
          animation: orb-float 12s ease-in-out infinite;
        }
        .orb-1 {
          width: 320px; height: 320px;
          background: rgba(100, 181, 246, 0.4);
          top: -80px; right: -60px;
          animation-delay: 0s;
        }
        .orb-2 {
          width: 240px; height: 240px;
          background: rgba(129, 212, 250, 0.35);
          bottom: -60px; left: -40px;
          animation-delay: -4s;
        }
        .orb-3 {
          width: 180px; height: 180px;
          background: rgba(206, 147, 216, 0.3);
          top: 50%; left: 20%;
          animation-delay: -8s;
        }
        [data-theme="dark"] .orb-1 { background: rgba(88, 157, 246, 0.2); }
        [data-theme="dark"] .orb-2 { background: rgba(100, 180, 255, 0.18); }
        [data-theme="dark"] .orb-3 { background: rgba(130, 170, 220, 0.15); }

        @keyframes orb-float {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33%  { transform: translate(30px, -20px) scale(1.05); }
          66%  { transform: translate(-20px, 15px) scale(0.95); }
        }

        .login-brand-content {
          position: relative;
          z-index: 1;
          color: #fff;
          text-align: center;
          max-width: 380px;
        }

        .login-logo {
          margin-bottom: 20px;
          display: inline-block;
          animation: logo-in 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        @keyframes logo-in {
          from { opacity: 0; transform: scale(0.8); }
          to   { opacity: 1; transform: scale(1); }
        }

        .login-brand-title {
          font-size: 32px;
          font-weight: 800;
          margin: 0 0 8px;
          letter-spacing: 1px;
          animation: fade-up 0.6s 0.1s cubic-bezier(0.16, 1, 0.3, 1) both;
        }

        .login-brand-desc {
          font-size: 15px;
          opacity: 0.8;
          margin: 0 0 40px;
          font-weight: 400;
          letter-spacing: 2px;
          animation: fade-up 0.6s 0.2s cubic-bezier(0.16, 1, 0.3, 1) both;
        }

        @keyframes fade-up {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }

        .login-features {
          display: flex;
          flex-direction: column;
          gap: 16px;
          text-align: left;
        }

        .login-feat-item {
          display: flex;
          align-items: center;
          gap: 12px;
          font-size: 14px;
          opacity: 0.85;
          animation: fade-up 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
          padding: 8px 12px;
          border-radius: 8px;
          background: rgba(255,255,255,0.06);
          transition: background 0.2s;
        }
        .login-feat-item:hover {
          background: rgba(255,255,255,0.12);
        }

        /* ============================
           右侧表单面板
           ============================ */
        .login-form-panel {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 32px;
          background: var(--bg-primary);
        }

        .login-form-inner {
          width: 100%;
          max-width: 400px;
          animation: fade-up 0.6s 0.3s cubic-bezier(0.16, 1, 0.3, 1) both;
        }

        /* 移动端顶部品牌 */
        .login-mobile-header {
          display: none;
          text-align: center;
          margin-bottom: 28px;
        }
        .login-logo-sm {
          width: 44px; height: 44px; border-radius: 12px;
          background: var(--accent); color: #fff;
          display: inline-flex; align-items: center; justify-content: center;
          font-size: 22px; font-weight: 700; margin-bottom: 12px;
        }

        /* 错误提示 */
        .login-error {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 0 14px;
          border-radius: 8px;
          background: var(--danger);
          color: #fff;
          font-size: 13px;
          margin-bottom: 20px;
          max-height: 0;
          overflow: hidden;
          opacity: 0;
          transition: max-height 0.3s ease, opacity 0.25s ease, padding 0.25s ease, margin 0.25s ease;
        }
        .login-error.show {
          max-height: 60px;
          opacity: 1;
          padding: 10px 14px;
          animation: shake 0.4s ease;
        }
        .login-error span { flex: 1; }
        .login-error-close {
          background: none; border: none; color: #fff; cursor: pointer;
          font-size: 18px; padding: 0 2px; line-height: 1; opacity: 0.7;
        }
        .login-error-close:hover { opacity: 1; }

        @keyframes shake {
          0%,100% { transform: translateX(0); }
          20%    { transform: translateX(-5px); }
          40%    { transform: translateX(5px); }
          60%    { transform: translateX(-3px); }
          80%    { transform: translateX(3px); }
        }

        /* 输入框 */
        .login-input-wrap {
          display: flex;
          align-items: center;
          border: 1.5px solid var(--border);
          border-radius: 10px;
          background: var(--bg-input, var(--bg-primary));
          margin-bottom: 14px;
          transition: border-color 0.2s, box-shadow 0.2s;
          overflow: hidden;
        }
        .login-input-wrap.focused {
          border-color: var(--accent);
          box-shadow: 0 0 0 3px var(--accent-light);
        }
        .login-input-wrap input {
          flex: 1;
          padding: 12px 0;
          border: none;
          font-size: 15px;
          outline: none;
          background: transparent;
          color: var(--text-primary);
        }
        .login-input-wrap input::placeholder { color: var(--text-muted); }
        .login-input-icon {
          padding: 0 0 0 14px;
          color: var(--text-muted);
          display: flex;
          transition: color 0.2s;
        }
        .login-input-wrap.focused .login-input-icon { color: var(--accent); }

        .login-eye {
          padding: 0 14px 0 0;
          background: none; border: none;
          cursor: pointer; color: var(--text-muted);
          display: flex; opacity: 0.5;
          transition: opacity 0.15s, color 0.2s;
        }
        .login-eye:hover { opacity: 1; }

        /* 记住我 — 自定义复选框 */
        .login-remember {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 24px;
          cursor: pointer;
          font-size: 13px;
          color: var(--text-secondary);
          user-select: none;
          width: fit-content;
        }
        .login-checkbox {
          width: 18px; height: 18px;
          border-radius: 5px;
          border: 1.5px solid var(--border);
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.15s;
          flex-shrink: 0;
        }
        .login-checkbox.checked {
          background: var(--accent);
          border-color: var(--accent);
        }

        /* 登录按钮 */
        .login-btn {
          width: 100%;
          padding: 13px 0;
          border-radius: 10px;
          border: none;
          background: var(--accent);
          color: #fff;
          font-size: 15px;
          font-weight: 600;
          cursor: pointer;
          transition: transform 0.1s, box-shadow 0.2s, background 0.2s;
          box-shadow: 0 2px 8px rgba(25,118,210,0.25);
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          letter-spacing: 2px;
        }
        .login-btn:hover {
          box-shadow: 0 4px 16px rgba(25,118,210,0.4);
        }
        .login-btn:active {
          transform: scale(0.98);
        }
        .login-btn.loading {
          background: var(--text-muted);
          box-shadow: none;
          cursor: not-allowed;
          letter-spacing: 0;
        }
        [data-theme="dark"] .login-btn {
          box-shadow: 0 2px 8px rgba(88,157,246,0.2);
        }
        [data-theme="dark"] .login-btn:hover {
          box-shadow: 0 4px 16px rgba(88,157,246,0.35);
        }

        .login-spinner {
          width: 16px; height: 16px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: #fff;
          border-radius: 50%;
          animation: login-spin 0.6s linear infinite;
        }
        @keyframes login-spin { to { transform: rotate(360deg); } }

        /* ============================
           响应式
           ============================ */
        @media (max-width: 800px) {
          .login-brand { display: none; }
          .login-mobile-header { display: block; }
          .login-form-panel {
            padding: 24px 20px;
          }
        }
      `}</style>
    </div>
  )
}
