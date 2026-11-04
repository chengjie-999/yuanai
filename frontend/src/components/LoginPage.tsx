import { useState, useEffect, useRef } from 'react'
import { useNavigate, Navigate, Link } from 'react-router-dom'
import { login, submitAppeal, agreeTerms, register, sendEmailCode, emailLogin } from '../api'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import Mascot from './Mascot'
import { ArrowLeftIcon, XIcon } from './icons'

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
  const [focused, setFocused] = useState<'user' | 'pw' | 'pw2' | 'name' | null>(null)
  // C7 冻结申诉（2026-10-29）
  const [appealContact, setAppealContact] = useState('')
  const [appealReason, setAppealReason] = useState('')
  const [appealMsg, setAppealMsg] = useState('')
  const [appealLoading, setAppealLoading] = useState(false)
  // C11 协议勾选（2026-10-29）：未勾选不可登录；已勾选过则记住（localStorage 安全读）
  const [agreed, setAgreed] = useState(() => {
    try { return localStorage.getItem('agreedTerms') === '1' } catch { return false }
  })
  // 注册模式（2026-10-30 开放注册）+ 邮箱验证码模式（R1' 2026-11-05）
  const [mode, setMode] = useState<'login' | 'register' | 'email'>('login')
  const [displayName, setDisplayName] = useState('')
  const [regPw2, setRegPw2] = useState('')
  const [email, setEmail] = useState('')
  const [emailCode, setEmailCode] = useState('')
  const [codeCountdown, setCodeCountdown] = useState(0)
  const [codeSending, setCodeSending] = useState(false)

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
    if (loading) return  // 防重复提交（连点登录按钮发多个请求）
    if (mode === 'register') { await handleRegister(); return }
    if (mode === 'email') { await handleEmailSubmit(); return }
    const u = username.trim()
    if (!u || !password) { setError('请填写用户名和密码'); return }
    if (password.length < 8) { setError('密码至少 8 个字符'); return }
    if (!agreed) { setError('请先阅读并同意《用户协议》与《隐私政策》'); return }
    setLoading(true)
    setError('')
    try {
      const data = await login(u, password)
      if (!data?.token) { setError('登录失败，服务器返回异常'); setLoading(false); return }
      handleLogin(data.token, data.user, remember)
      agreeTerms()  // C11：协议接受留痕（fire-and-forget）
      if (data.user?.theme && data.user.theme !== theme) setTheme(data.user.theme)
      navigate('/chat', { replace: true })
    } catch (e: any) {
      setError(e.message || '操作失败')
    }
    setLoading(false)
  }

  // 注册（2026-10-30 开放）：本地校验 → 后端注册 → 自动登录进 /chat
  const handleRegister = async () => {
    const u = username.trim()
    if (!u || !password) { setError('请填写用户名和密码'); return }
    if (u.length < 3) { setError('用户名至少 3 个字符'); return }
    if (/admin/i.test(u) || u.includes('管理员')) { setError('用户名不能包含 admin/管理员'); return }
    if (password.length < 8) { setError('密码至少 8 个字符'); return }
    if (password !== regPw2) { setError('两次输入的密码不一致'); return }
    if (!agreed) { setError('请先阅读并同意《用户协议》与《隐私政策》'); return }
    setLoading(true)
    setError('')
    try {
      await register(u, password, displayName.trim(), true)  // 协议后端强制 + 留痕
      // 注册成功自动登录（同一凭据）
      const data = await login(u, password)
      if (!data?.token) { setError('注册成功，请使用新账号登录'); setMode('login'); setLoading(false); return }
      try { localStorage.setItem('agreedTerms', '1') } catch { /* 忽略 */ }
      handleLogin(data.token, data.user, remember)
      if (data.user?.theme && data.user.theme !== theme) setTheme(data.user.theme)
      navigate('/chat', { replace: true })
    } catch (e: any) {
      setError(e.message || '注册失败')
    }
    setLoading(false)
  }

  // R1' 邮箱验证码：发送验证码（60s 冷却倒计时）
  const handleEmailSend = async () => {
    const em = email.trim()
    if (!em) { setError('请先填写邮箱地址'); return }
    if (!/^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(em)) { setError('邮箱格式不正确'); return }
    if (codeCountdown > 0 || codeSending) return
    setCodeSending(true)
    setError('')
    try {
      await sendEmailCode(em)
      setCodeCountdown(60)
    } catch (e: any) {
      setError(e.message || '验证码发送失败')
    }
    setCodeSending(false)
  }

  // 倒计时（60s → 0 可重发）
  useEffect(() => {
    if (codeCountdown <= 0) return
    const t = setTimeout(() => setCodeCountdown(c => c - 1), 1000)
    return () => clearTimeout(t)
  }, [codeCountdown])

  // R1' 邮箱验证码登录（注册登录合一，自动登录）
  const handleEmailSubmit = async () => {
    const em = email.trim()
    if (!em || !emailCode.trim()) { setError('请填写邮箱和验证码'); return }
    if (emailCode.trim().length !== 6) { setError('验证码为 6 位数字'); return }
    if (!agreed) { setError('请先阅读并同意《用户协议》与《隐私政策》'); return }
    setLoading(true)
    setError('')
    try {
      const data = await emailLogin(em, emailCode.trim(), true)
      if (!data?.token) { setError('登录失败，服务器返回异常'); setLoading(false); return }
      try { localStorage.setItem('agreedTerms', '1') } catch { /* 忽略 */ }
      handleLogin(data.token, data.user, remember)
      agreeTerms()  // C11：协议接受留痕（自动注册已留痕，此处幂等）
      if (data.user?.theme && data.user.theme !== theme) setTheme(data.user.theme)
      navigate('/chat', { replace: true })
    } catch (e: any) {
      setError(e.message || '登录失败')
    }
    setLoading(false)
  }

  const handleAppeal = async () => {
    if (!username.trim() || !appealReason.trim() || appealLoading) return
    setAppealLoading(true)
    setAppealMsg('')
    try {
      const msg = await submitAppeal(username.trim(), appealContact.trim(), appealReason.trim())
      setAppealMsg(msg)
      setAppealReason('')
    } catch (e: any) {
      setAppealMsg(e.message || '申诉提交失败')
    }
    setAppealLoading(false)
  }

  if (token) return <Navigate to="/chat" replace />

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
        <p className="login-brand-desc">云边协同 · 对话即执行</p>

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
        {/* 返回官网首页 */}
        <Link to="/" className="login-back-home" aria-label="返回首页">
          <ArrowLeftIcon size={14} />
          返回首页
        </Link>

        {/* 移动端显示的品牌标识 */}
        <div className="login-mobile-header">
          <Mascot size={56} />
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 4px' }}>{mode === 'register' ? '创建账号' : '欢迎回来'}</h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>{mode === 'register' ? '注册后即可使用全部功能' : '登录小元AI账号以继续'}</p>
        </div>

        {/* 登录方式双 tab（R1' 2026-11-05）：密码登录 / 验证码登录 */}
        {mode !== 'register' && (
          <div className="login-tabs" role="tablist">
            <button role="tab" aria-selected={mode === 'login'}
              className={`login-tab ${mode === 'login' ? 'active' : ''}`}
              onClick={() => { setMode('login'); setError('') }}>
              密码登录
            </button>
            <button role="tab" aria-selected={mode === 'email'}
              className={`login-tab ${mode === 'email' ? 'active' : ''}`}
              onClick={() => { setMode('email'); setError('') }}>
              验证码登录
            </button>
          </div>
        )}

        {/* 错误提示 */}
        <div className={`login-error ${error ? 'show' : ''}`}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          <span>{error || ''}</span>
          <button onClick={() => setError('')} className="login-error-close" title="关闭" aria-label="关闭"><XIcon size={14} /></button>
        </div>

        {/* C7 冻结申诉（2026-10-29）：登录提示冻结时出现，公开申诉无需登录 */}
        {error.includes('冻结') && (
          <div style={{ marginBottom: 14, padding: 12, borderRadius: 10, background: 'var(--warning-soft)', border: '1px solid var(--warning)' }}>
            <div style={{ fontSize: 12.5, color: 'var(--warning)', fontWeight: 600, marginBottom: 8 }}>对冻结有异议？提交申诉，平台将在 3 个工作日内反馈</div>
            <input value={appealContact} onChange={(e) => setAppealContact(e.target.value)}
              placeholder="联系方式（邮箱/手机号，用于接收处理结果）"
              style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)', marginBottom: 8 }} />
            <input value={appealReason} onChange={(e) => setAppealReason(e.target.value)}
              placeholder="申诉理由"
              style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)', marginBottom: 8 }} />
            {appealMsg && <div style={{ fontSize: 12, color: 'var(--success)', marginBottom: 6 }}>{appealMsg}</div>}
            <button onClick={handleAppeal} disabled={appealLoading || !appealReason.trim()}
              style={{ padding: '6px 16px', borderRadius: 6, border: 'none', background: 'var(--warning)', color: '#fff', fontSize: 13, cursor: appealReason.trim() && !appealLoading ? 'pointer' : 'default', opacity: appealReason.trim() && !appealLoading ? 1 : 0.55 }}>
              {appealLoading ? '提交中...' : '提交申诉'}
            </button>
          </div>
        )}

        {/* R1' 邮箱验证码模式：邮箱 + 验证码 */}
        {mode === 'email' && (
          <>
            <div className={`login-input-wrap ${focused === 'user' ? 'focused' : ''}`}>
              <span className="login-input-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>
                </svg>
              </span>
              <input
                value={email}
                onChange={e => setEmail(e.target.value)}
                onFocus={() => setFocused('user')}
                onBlur={() => setFocused(null)}
                onKeyDown={e => e.key === 'Enter' && handleEmailSubmit()}
                placeholder="邮箱地址"
                type="email"
                autoComplete="email"
              />
            </div>
            <div className={`login-input-wrap ${focused === 'pw' ? 'focused' : ''}`}>
              <span className="login-input-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
              </span>
              <input
                value={emailCode}
                onChange={e => setEmailCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                onFocus={() => setFocused('pw')}
                onBlur={() => setFocused(null)}
                onKeyDown={e => e.key === 'Enter' && handleEmailSubmit()}
                placeholder="6 位验证码"
                inputMode="numeric"
                autoComplete="one-time-code"
              />
              <button type="button" className="login-code-btn"
                onClick={handleEmailSend}
                disabled={codeCountdown > 0 || codeSending}
                tabIndex={-1}>
                {codeSending ? '发送中...' : codeCountdown > 0 ? `${codeCountdown}s 后重发` : '发送验证码'}
              </button>
            </div>
            <p className="login-field-hint">未注册的邮箱验证通过后将自动创建账号</p>
          </>
        )}

        {/* 用户名 */}
        {mode !== 'email' && (
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
        )}
        {/* 注册模式：用户名规则提示（不限制字符类型，仅长度 + 防冒充） */}
        {mode === 'register' && (
          <p className="login-field-hint">3 位以上，中文/字母/数字/符号均可；不能含 admin/管理员</p>
        )}

        {/* 注册模式：显示名（选填） */}
        {mode === 'register' && (
          <div className={`login-input-wrap ${focused === 'name' ? 'focused' : ''}`}>
            <span className="login-input-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
              </svg>
            </span>
            <input
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              onFocus={() => setFocused('name')}
              onBlur={() => setFocused(null)}
              onKeyDown={e => e.key === 'Enter' && handleSubmit()}
              placeholder="显示名（选填）"
              autoComplete="nickname"
            />
          </div>
        )}

        {/* 密码 */}
        {mode !== 'email' && (<>
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
            placeholder={mode === 'register' ? '密码（至少 8 位）' : '密码'}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
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
        {/* 注册模式：密码规则提示（任意字符均可，仅限长度） */}
        {mode === 'register' && (
          <p className="login-field-hint">至少 8 位，任意字符均可（中文/字母/数字/符号）</p>
        )}

        {/* 注册模式：确认密码 */}
        {mode === 'register' && (
          <div className={`login-input-wrap ${focused === 'pw2' ? 'focused' : ''}`}>
            <span className="login-input-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
            </span>
            <input
              value={regPw2}
              onChange={e => setRegPw2(e.target.value)}
              onFocus={() => setFocused('pw2')}
              onBlur={() => setFocused(null)}
              onKeyDown={e => e.key === 'Enter' && handleSubmit()}
              type={showPw ? 'text' : 'password'}
              placeholder="再次输入密码"
              autoComplete="new-password"
            />
          </div>
        )}
        </>)}

        {/* 记住我（仅登录模式） */}
        {mode === 'login' && (
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
        )}

        {/* C11 协议勾选（2026-10-29）：未勾选不可登录/注册；登录后留痕（POST /auth/agree），注册后端强制 */}
        <label className="login-remember" style={{ marginTop: 10 }}>
          <span className={`login-checkbox ${agreed ? 'checked' : ''}`}>
            {agreed && (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            )}
          </span>
          <input type="checkbox" checked={agreed} onChange={e => {
            setAgreed(e.target.checked)
            try { localStorage.setItem('agreedTerms', e.target.checked ? '1' : '0') } catch { /* 忽略 */ }
          }} style={{ display: 'none' }}/>
          <span style={{ fontSize: 12.5, color: 'var(--text-secondary)' }}>
            我已阅读并同意
            <Link to="/terms" target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>《用户协议》</Link>和
            <Link to="/privacy" target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>《隐私政策》</Link>
          </span>
        </label>

        {/* 提交按钮（登录/注册/验证码登录） */}
        <button className={`login-btn ${loading ? 'loading' : ''}`} onClick={handleSubmit} disabled={loading || !agreed}
          style={{ opacity: loading || !agreed ? 0.55 : 1 }}>
          {loading ? (
            <><span className="login-spinner"/> {mode === 'register' ? '注册中...' : '登录中...'}</>
          ) : mode === 'register' ? '注  册' : mode === 'email' ? '登录 / 注册' : '登  录'}
        </button>

        {/* 模式切换（2026-10-30 开放注册；2026-11-05 加邮箱验证码） */}
        <p className="login-no-register" style={{ fontSize: 13 }}>
          {mode === 'login' ? (
            <>没有账号？<button onClick={() => { setMode('register'); setError(''); setRegPw2('') }}
              style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 13, padding: 0 }}>立即注册</button></>
          ) : mode === 'register' ? (
            <>已有账号？<button onClick={() => { setMode('login'); setError('') }}
              style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 13, padding: 0 }}>去登录</button></>
          ) : (
            <>使用密码登录？<button onClick={() => { setMode('login'); setError('') }}
              style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 13, padding: 0 }}>切换</button></>
          )}
          <br />
          <span style={{ fontSize: 12 }}>微信 <b>17852428208</b> · <a href="mailto:chengjie2017020@163.com">chengjie2017020@163.com</a></span>
        </p>

        {/* 忘记密码指引（2026-10-30）：无自助找回，管理员重置 */}
        <p className="login-no-register" style={{ marginTop: 0, fontSize: 12 }}>
          忘记密码？请联系管理员为你重置密码
        </p>

        {/* C11 ICP 备案页脚（登录页同展示） */}
        <div style={{ textAlign: 'center', marginTop: 16, fontSize: 11, color: 'var(--text-muted)' }}>
          <a href="https://beian.miit.gov.cn/" target="_blank" rel="noreferrer" style={{ color: 'var(--text-muted)' }}>鲁ICP备2026043700号</a>
        </div>
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
          min-height: 100dvh;
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

        /* 登录方式双 tab（R1'） */
        .login-tabs {
          display: flex;
          background: var(--bg-tertiary);
          border-radius: 8px;
          padding: 3px;
          margin-bottom: 18px;
          gap: 3px;
        }
        .login-tab {
          flex: 1;
          padding: 8px 0;
          border: none;
          border-radius: 6px;
          background: transparent;
          color: var(--text-secondary);
          font-size: 13.5px;
          cursor: pointer;
          transition: all 0.15s;
        }
        .login-tab.active {
          background: var(--bg-input);
          color: var(--text-primary);
          font-weight: 600;
          box-shadow: 0 1px 4px var(--shadow-sm);
        }

        /* 验证码发送按钮 */
        .login-code-btn {
          margin-right: 8px;
          padding: 6px 10px;
          border: none;
          border-radius: 6px;
          background: var(--accent-soft);
          color: var(--accent);
          font-size: 12.5px;
          cursor: pointer;
          white-space: nowrap;
          transition: opacity 0.15s;
        }
        .login-code-btn:disabled {
          cursor: default;
          opacity: 0.6;
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
          padding: 2px; line-height: 1; opacity: 0.7; display: flex;
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
          padding: 13px 14px 13px 0;
          border: none;
          font-size: 15px;
          outline: none;
          background: transparent;
          color: var(--text-primary);
        }
        .login-input-wrap input::placeholder { color: var(--text-muted); }
        /* 注册模式：字段规则提示小字（紧贴输入框下方） */
        .login-field-hint {
          font-size: 12px;
          color: var(--text-muted);
          margin: -8px 2px 14px;
          line-height: 1.5;
        }
        .login-input-icon {
          padding: 0 8px 0 14px;
          color: var(--text-muted);
          display: flex;
          transition: color 0.2s;
        }
        .login-input-wrap.focused .login-input-icon { color: var(--accent); }

        .login-eye {
          padding: 0 14px 0 8px;
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
          box-shadow: 0 2px 8px rgba(77,166,255,0.2);
        }
        [data-theme="dark"] .login-btn:hover {
          box-shadow: 0 4px 16px rgba(77,166,255,0.35);
        }

        /* 暗夜模式 — 输入框（与全局 --bg-input 一致） */
        [data-theme="dark"] .login-input-wrap {
          background: var(--bg-tertiary);
          border-color: var(--border);
        }
        [data-theme="dark"] .login-input-wrap.focused {
          background: var(--bg-input);
          border-color: var(--accent);
        }
        [data-theme="dark"] .login-input-wrap input:-webkit-autofill,
        [data-theme="dark"] .login-input-wrap input:-webkit-autofill:hover,
        [data-theme="dark"] .login-input-wrap input:-webkit-autofill:focus {
          -webkit-box-shadow: 0 0 0 30px var(--bg-tertiary) inset !important;
          -webkit-text-fill-color: var(--text-primary) !important;
          caret-color: var(--text-primary);
        }

        .login-spinner {
          width: 16px; height: 16px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: #fff;
          border-radius: 50%;
          animation: login-spin 0.6s linear infinite;
        }
        @keyframes login-spin { to { transform: rotate(360deg); } }

        /* 返回首页 */
        .login-back-home {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 13px;
          color: var(--text-secondary);
          text-decoration: none;
          margin-bottom: 24px;
          transition: color 0.15s;
        }
        .login-back-home:hover { color: var(--accent); }

        /* 注册提示 */
        .login-no-register {
          margin: 20px 0 0;
          text-align: center;
          font-size: 12px;
          color: var(--text-muted);
          line-height: 1.8;
        }
        .login-no-register b {
          color: var(--text-secondary);
          font-weight: 600;
        }
        .login-no-register a {
          color: var(--accent);
          text-decoration: none;
        }
        .login-no-register a:hover { text-decoration: underline; }

        /* ============================
           响应式
           ============================ */
        /* 平板：缩小左侧品牌面板 */
        @media (max-width: 1024px) {
          .login-brand {
            flex: 0 0 40%;
            padding: 32px;
          }
          .login-brand-title { font-size: 26px; }
          .login-brand-desc { font-size: 13px; margin-bottom: 28px; }
          .login-feat-item { font-size: 13px; padding: 6px 10px; }
        }

        /* 手机：隐藏品牌面板，表单居中 */
        @media (max-width: 800px) {
          .login-page {
            flex-direction: column;
          }
          .login-brand { display: none; }
          .login-mobile-header { display: block; }
          .login-form-panel {
            flex: 1;
            padding: 40px 20px;
            align-items: flex-start;
          }
          .login-form-inner {
            max-width: 100%;
          }
          .login-input-wrap {
            border-radius: 12px;
          }
          .login-input-wrap input {
            font-size: 16px;  /* 防止 iOS 自动缩放 */
            padding: 14px 14px 14px 0;
          }
          .login-input-icon {
            padding: 0 8px 0 16px;
          }
          .login-eye {
            padding: 0 16px 0 8px;
          }
          .login-btn {
            padding: 15px 0;
            font-size: 16px;
            border-radius: 12px;
          }
          .login-remember {
            margin-bottom: 28px;
          }
        }

        /* 小屏手机 */
        @media (max-width: 400px) {
          .login-form-panel {
            padding: 24px 16px;
          }
          .login-mobile-header {
            margin-bottom: 20px;
          }
        }
      `}</style>
    </div>
  )
}
