import { useState, useCallback, useEffect, lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation, useNavigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { ThemeProvider, useTheme } from './contexts/ThemeContext'
import AgentStatus from './components/AgentStatus'
import { ErrorBoundary } from './components/ErrorBoundary'

/* 路由级懒加载：公开页访客无需下载聊天/后台代码，首屏体积大减 */
const ChatPage = lazy(() => import('./components/ChatPage'))
const LoginPage = lazy(() => import('./components/LoginPage'))
const LandingPage = lazy(() => import('./components/LandingPage'))
const AboutPage = lazy(() => import('./components/AboutPage'))
const AdminPage = lazy(() => import('./components/AdminPage'))
const UserPage = lazy(() => import('./components/UserPage'))
const SettingsPage = lazy(() => import('./components/SettingsPage'))
const AgentPage = lazy(() => import('./components/AgentPage'))
const AgentAnalysisPage = lazy(() => import('./pages/AgentAnalysisPage'))
const AgentAutomationPage = lazy(() => import('./pages/AgentAutomationPage'))
const AgentKnowledgePage = lazy(() => import('./pages/AgentKnowledgePage'))
const RFMDashboard = lazy(() => import('./pages/RFMDashboard'))
const AnalysisDashboard = lazy(() => import('./pages/AnalysisDashboard'))
const MedicalPage = lazy(() => import('./components/MedicalPage'))
const CollectionRecordsPage = lazy(() => import('./components/CollectionRecordsPage'))

/* 懒加载页面统一的加载占位（保持 Header 不闪） */
function PageLoading() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '15vh 0', color: 'var(--text-muted)', fontSize: 13, gap: 8,
    }}>
      <span style={{
        width: 14, height: 14, border: '2px solid var(--border)',
        borderTopColor: 'var(--accent)', borderRadius: '50%',
        display: 'inline-block', animation: 'spin 0.8s linear infinite',
      }} />
      加载中...
    </div>
  )
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token, loading } = useAuth()
  if (loading) return null
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { token, loading, isAdmin } = useAuth()
  if (loading) return null
  if (!token) return <Navigate to="/login" replace />
  if (!isAdmin) return <Navigate to="/chat" replace />
  return <>{children}</>
}

function AppLayout() {
  const { user, logout, isAdmin } = useAuth()
  const { isDark, toggle: toggleTheme } = useTheme()
  const location = useLocation()
  const navigate = useNavigate()
  const [resetKey, setResetKey] = useState(0)

  // 点击左上角品牌 → 回官网首页（聊天会话重置，回来时是全新欢迎页）
  const goHome = useCallback(() => {
    setResetKey((k) => k + 1)
    navigate('/')
  }, [navigate])

  const isActive = (path: string) => location.pathname === path || (path === '/chat/admin' && location.pathname.startsWith('/chat/admin'))

  const navLinkStyle = (path: string) => ({
    background: 'transparent', border: 'none',
    color: isActive(path) ? 'var(--text-primary)' : 'var(--text-secondary)',
    fontWeight: (isActive(path) ? 600 : 400) as any, fontSize: 14,
    padding: '0 14px', height: 52, cursor: 'pointer',
    borderBottom: isActive(path) ? '2px solid var(--text-primary)' : '2px solid transparent',
    transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 6,
    textDecoration: 'none',
  })

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header className="app-header" style={{
        background: 'var(--header-bg)', borderBottom: '1px solid var(--border)',
        padding: '0 12px', display: 'flex', alignItems: 'center', height: 52, flexShrink: 0,
        gap: 8,
      }}>
        <span className="brand" onClick={goHome} style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: -0.3, cursor: 'pointer', flexShrink: 0, userSelect: 'none' }}>
          小元AI
        </span>
        <nav style={{ display: 'flex', gap: 0 }}>
          <Link to="/chat" style={navLinkStyle('/chat')}>对话</Link>
          {isAdmin && (
            <Link to="/chat/admin" style={navLinkStyle('/chat/admin')}>管理</Link>
          )}
        </nav>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button onClick={toggleTheme} aria-label={isDark ? '切换亮色模式' : '切换暗色模式'} title={isDark ? '切换亮色模式' : '切换暗色模式'}
            className="theme-toggle"
            style={{
              width: 44, height: 24, borderRadius: 12, border: 'none',
              background: isDark ? '#45494a' : '#d0d7de',
              cursor: 'pointer', position: 'relative', padding: 0, flexShrink: 0,
              transition: 'background 0.3s',
            }}
          >
            <span className="toggle-knob" style={{
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
          <span className="hide-mobile">
            <Link to="/chat/agent" style={{ textDecoration: 'none' }}>
              <AgentStatus userId={user?.id} />
            </Link>
          </span>
          <Link to="/chat/user" style={{
            fontSize: 13, color: 'var(--accent)', cursor: 'pointer', textDecoration: 'none',
            whiteSpace: 'nowrap',
            borderBottom: location.pathname === '/chat/user' ? '1px solid var(--accent)' : '1px solid transparent',
          }}>{user?.username || user?.display_name}</Link>
          <Link to="/chat/settings" style={{
            fontSize: 13, color: location.pathname === '/chat/settings' ? 'var(--text-primary)' : 'var(--text-secondary)',
            cursor: 'pointer', textDecoration: 'none', whiteSpace: 'nowrap',
            fontWeight: location.pathname === '/chat/settings' ? 600 : 400,
          }}>设置</Link>
        </div>
      </header>
      <main style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        <ErrorBoundary>
          <Suspense fallback={<PageLoading />}>
          <Routes>
            <Route path="/" element={<ChatPage key={resetKey} user={user} />} />
            <Route path="/user" element={<UserPage user={user} onLogout={logout} />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/agent" element={<AgentPage userId={user?.id} />} />
            <Route path="/agent/analysis" element={<AgentAnalysisPage />} />
            <Route path="/agent/automation" element={<AgentAutomationPage />} />
            <Route path="/agent/knowledge" element={<AgentKnowledgePage />} />
            <Route path="/agent/rfm" element={<RFMDashboard />} />
            <Route path="/agent/dashboard/:sessionId" element={<AnalysisDashboard />} />
            <Route path="/agent/medical" element={<MedicalPage />} />
            <Route path="/agent/records" element={<CollectionRecordsPage />} />
            <Route path="/admin/*" element={
              <AdminRoute><AdminPage isAdmin={isAdmin} /></AdminRoute>
            } />
          </Routes>
          </Suspense>
        </ErrorBoundary>
      </main>
    </div>
  )
}

/* 预取常用页面代码：页面加载完成后空闲时间提前下载，切换页面时秒开 */
function AppInner() {
  const { token, isAdmin } = useAuth()
  useEffect(() => {
    const timer = setTimeout(() => {
      if (token) {
        // 登录用户：预取聊天/个人/设置（admin 再预取后台）
        import('./components/ChatPage')
        import('./components/UserPage')
        import('./components/SettingsPage')
        if (isAdmin) import('./components/AdminPage')
      } else {
        // 访客：预取关于我与登录页（首页已加载）
        import('./components/AboutPage')
        import('./components/LoginPage')
      }
    }, 1500)
    return () => clearTimeout(timer)
  }, [token, isAdmin])

  return (
    <Suspense fallback={<PageLoading />}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/chat/*" element={<ProtectedRoute><AppLayout /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <AppInner />
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}
