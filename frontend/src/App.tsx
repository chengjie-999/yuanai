import { Component } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
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
          <h3 style={{ color: '#e53935' }}>页面异常</h3>
          <p style={{ fontSize: 13, color: '#999', margin: '8px 0' }}>{this.state.error}</p>
          <button onClick={() => window.location.reload()} style={{ marginTop: 12, padding: '6px 16px', cursor: 'pointer', border: '1px solid #ddd', borderRadius: 6, background: '#fff', fontSize: 13 }}>刷新页面</button>
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
  const location = useLocation()

  const isActive = (path: string) => location.pathname === path || (path === '/admin' && location.pathname.startsWith('/admin'))

  const navLinkStyle = (path: string) => ({
    background: 'transparent', border: 'none',
    color: isActive(path) ? '#333' : '#999',
    fontWeight: (isActive(path) ? 600 : 400) as any, fontSize: 14,
    padding: '0 14px', height: 52, cursor: 'pointer',
    borderBottom: isActive(path) ? '2px solid #333' : '2px solid transparent',
    transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 6,
    textDecoration: 'none',
  })

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{
        background: '#fff', borderBottom: '1px solid #e5e5e5',
        padding: '0 20px', display: 'flex', alignItems: 'center', height: 52, flexShrink: 0,
      }}>
        <Link to="/" style={{ fontSize: 17, fontWeight: 700, color: '#333', marginRight: 32, letterSpacing: -0.3, textDecoration: 'none' }}>
          小元AI
        </Link>
        <nav style={{ display: 'flex', gap: 2 }}>
          <Link to="/" style={navLinkStyle('/')}>对话</Link>
          {isAdmin && (
            <Link to="/admin" style={navLinkStyle('/admin')}>后台管理</Link>
          )}
        </nav>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Link to="/agent" style={{ textDecoration: 'none' }}>
            <AgentStatus userId={user?.id} />
          </Link>
          <Link to="/user" style={{
            fontSize: 13, color: '#1976d2', cursor: 'pointer', textDecoration: 'none',
            borderBottom: location.pathname === '/user' ? '1px solid #1976d2' : '1px solid transparent',
          }}>{user?.username || user?.display_name}</Link>
        </div>
      </header>
      <main style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<ChatPage user={user} />} />
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
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/*" element={<ProtectedRoute><AppLayout /></ProtectedRoute>} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
