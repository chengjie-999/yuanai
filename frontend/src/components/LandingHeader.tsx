import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'

/* ============================================================
   公开页共享 Header — 官网首页 / 关于我页复用
   品牌 + 导航（首页/关于我们） + 主题切换 + 登录态按钮
   ============================================================ */

export default function LandingHeader() {
  const { token, loading } = useAuth()
  const { isDark, toggle: toggleTheme } = useTheme()
  const location = useLocation()

  const navStyle = (path: string) => ({
    display: 'inline-flex', alignItems: 'center', height: 34, padding: '0 12px',
    borderRadius: 17, fontSize: 13, textDecoration: 'none',
    color: location.pathname === path ? 'var(--accent)' : 'var(--text-secondary)',
    background: location.pathname === path ? 'var(--accent-light)' : 'transparent',
    fontWeight: location.pathname === path ? 600 : 400,
    transition: 'all 0.15s',
  })

  return (
    <header className="landing-header">
      <Link to="/" className="landing-brand">
        <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: -0.3 }}>
          小元AI
        </span>
      </Link>
      <nav style={{ display: 'flex', gap: 4, marginLeft: 16 }}>
        <Link to="/" style={navStyle('/')}>首页</Link>
        <Link to="/about" style={navStyle('/about')}>关于我们</Link>
      </nav>
      <div style={{ flex: 1 }} />
      <button onClick={toggleTheme} aria-label={isDark ? '切换亮色模式' : '切换暗色模式'} title={isDark ? '切换亮色模式' : '切换暗色模式'}
        className="theme-toggle"
        style={{
          width: 44, height: 24, borderRadius: 12, border: 'none',
          background: isDark ? '#45494a' : '#d0d7de',
          cursor: 'pointer', position: 'relative', padding: 0, flexShrink: 0,
          transition: 'background 0.3s',
        }}
      >
        <span style={{
          position: 'absolute', top: 2, left: isDark ? 22 : 2,
          width: 20, height: 20, borderRadius: '50%',
          background: isDark ? '#4da6ff' : '#ffffff',
          transition: 'left 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
        }}>
          {isDark ? (
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
          ) : (
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
          )}
        </span>
      </button>
      {/* 登录态按钮：加载中渲染占位，有 token 显示"进入对话"，否则"登录" */}
      {loading ? (
        <span className="landing-auth-btn landing-auth-placeholder" />
      ) : token ? (
        <Link to="/chat" className="landing-auth-btn landing-auth-btn-primary">进入对话</Link>
      ) : (
        <Link to="/login" className="landing-auth-btn landing-auth-btn-ghost">登录</Link>
      )}

      <style>{`
        /* ============================
           公开页 Header — 共享样式
           ============================ */
        .landing-header {
          position: sticky;
          top: 0;
          z-index: 50;
          display: flex;
          align-items: center;
          gap: 12px;
          height: 56px;
          padding: 0 24px;
          background: var(--bg-primary);
          border-bottom: 1px solid var(--border);
        }
        .landing-brand {
          text-decoration: none;
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
          flex-shrink: 0;
        }

        /* 登录态按钮 */
        .landing-auth-btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          height: 34px;
          padding: 0 18px;
          border-radius: 17px;
          font-size: 13px;
          font-weight: 600;
          text-decoration: none;
          white-space: nowrap;
          transition: all 0.15s;
        }
        .landing-auth-btn-primary {
          background: var(--accent);
          color: #fff;
          box-shadow: 0 2px 8px rgba(25,118,210,0.25);
        }
        .landing-auth-btn-primary:hover {
          box-shadow: 0 4px 16px rgba(25,118,210,0.4);
          transform: translateY(-1px);
        }
        .landing-auth-btn-ghost {
          border: 1px solid var(--border);
          background: transparent;
          color: var(--text-primary);
        }
        .landing-auth-btn-ghost:hover {
          border-color: var(--accent);
          color: var(--accent);
        }
        /* 认证加载中的占位（避免布局抖动） */
        .landing-auth-placeholder {
          width: 74px;
          background: var(--border);
          opacity: 0.4;
          pointer-events: none;
        }
        [data-theme="dark"] .landing-auth-btn-primary {
          box-shadow: 0 2px 8px rgba(77,166,255,0.2);
        }
        [data-theme="dark"] .landing-auth-btn-primary:hover {
          box-shadow: 0 4px 16px rgba(77,166,255,0.35);
        }

        /* 手机：缩小 Header 内边距 */
        @media (max-width: 800px) {
          .landing-header { padding: 0 16px; }
        }
      `}</style>
    </header>
  )
}
