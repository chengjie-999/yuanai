import { Component, useState, useCallback } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation, useNavigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { ThemeProvider, useTheme } from './contexts/ThemeContext'
import ChatPage from './components/ChatPage'
import LoginPage from './components/LoginPage'
import AdminPage from './components/AdminPage'
import UserPage from './components/UserPage'
import AgentPage from './components/AgentPage'
import AgentStatus from './components/AgentStatus'
import AgentAnalysisPage from './pages/AgentAnalysisPage'
import AgentAutomationPage from './pages/AgentAutomationPage'
import AgentKnowledgePage from './pages/AgentKnowledgePage'

class ErrorBoundary extends Component<{ children: React.ReactNode }, { hasError: boolean; error: string }> {
  state = { hasError: false, error: '' }
  static getDerivedStateFromError(e: Error) { return { hasError: true, error: e.message } }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, textAlign: 'center' }}>
          <h3 style={{ color: 'var(--danger)' }}>页面异常</h3>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '8px 0' }}>{this.state.error}</p>
          <button onClick={() => window.location.reload()} style={{ marginTop: 12, padding: '6px 16px', cursor: 'pointer', border: '1px solid var(--border)', borderRadius: 6, background: 'var(--bg-primary)', fontSize: 13, color: 'var(--text-primary)' }}>刷新页面</button>
        </div>
      )
    }
    return this.props.children
  }
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
  if (!isAdmin) return <Navigate to="/" replace />
  return <>{children}</>
}

function AppLayout() {
  const { user, logout, isAdmin } = useAuth()
  const { isDark, toggle: toggleTheme } = useTheme()
  const location = useLocation()
  const navigate = useNavigate()
  const [resetKey, setResetKey] = useState(0)

  const goHome = useCallback(() => {
    setResetKey((k) => k + 1)
    if (location.pathname !== '/') navigate('/')
  }, [location.pathname, navigate])

  const isActive = (path: string) => location.pathname === path || (path === '/admin' && location.pathname.startsWith('/admin'))

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
      <header style={{
        background: 'var(--header-bg)', borderBottom: '1px solid var(--border)',
        padding: '0 12px', display: 'flex', alignItems: 'center', height: 52, flexShrink: 0,
        gap: 8,
      }}>
        <span onClick={goHome} style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: -0.3, cursor: 'pointer', flexShrink: 0, userSelect: 'none' }}>
          小元AI
        </span>
        <nav style={{ display: 'flex', gap: 0 }}>
          <Link to="/" style={navLinkStyle('/')}>对话</Link>
          {isAdmin && (
            <Link to="/admin" style={navLinkStyle('/admin')}>管理</Link>
          )}
        </nav>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button onClick={toggleTheme} title={isDark ? '切换亮色模式' : '切换暗色模式'}
            style={{
              width: 44, height: 24, borderRadius: 12, border: 'none',
              background: isDark ? '#3a3a4a' : '#d0d7de',
              cursor: 'pointer', position: 'relative', padding: 0, flexShrink: 0,
              transition: 'background 0.3s',
            }}
          >
            <span style={{
              position: 'absolute', top: 2, left: isDark ? 22 : 2,
              width: 20, height: 20, borderRadius: '50%',
              background: isDark ? '#58a6ff' : '#ffffff',
              transition: 'left 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, lineHeight: 1, boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
            }}>
              {isDark ? '🌙' : '☀️'}
            </span>
          </button>
          <span className="hide-mobile">
            <Link to="/agent" style={{ textDecoration: 'none' }}>
              <AgentStatus userId={user?.id} />
            </Link>
          </span>
          <Link to="/user" style={{
            fontSize: 13, color: 'var(--accent)', cursor: 'pointer', textDecoration: 'none',
            whiteSpace: 'nowrap',
            borderBottom: location.pathname === '/user' ? '1px solid var(--accent)' : '1px solid transparent',
          }}>{user?.username || user?.display_name}</Link>
        </div>
      </header>
      <main style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<ChatPage key={resetKey} user={user} />} />
            <Route path="/user" element={<UserPage user={user} onLogout={logout} />} />
            <Route path="/agent" element={<AgentPage userId={user?.id} />} />
            <Route path="/agent/analysis" element={<AgentAnalysisPage />} />
            <Route path="/agent/automation" element={<AgentAutomationPage />} />
            <Route path="/agent/knowledge" element={<AgentKnowledgePage />} />
            <Route path="/admin/*" element={
              <AdminRoute><AdminPage isAdmin={isAdmin} /></AdminRoute>
            } />
          </Routes>
        </ErrorBoundary>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/*" element={<ProtectedRoute><AppLayout /></ProtectedRoute>} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}
